"""
tools/github_tools.py — All GitHub API interactions.

Keeps PyGithub calls isolated so agents never touch the network directly.
Uses tenacity for automatic retry with exponential back-off.
"""

from __future__ import annotations

import re
from typing import List, Optional
import os
import httpx
from github import Github, GithubException
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import get_settings
from state import PRMetadata
from utils.logger import get_logger

log = get_logger("github_tools")


def _parse_pr_url(pr_url: str) -> tuple[str, int]:
    """
    Extract (owner/repo, pr_number) from any of these URL forms:
      • https://github.com/owner/repo/pull/123
      • owner/repo#123
    """
    pattern = r"github\.com/([^/]+/[^/]+)/pull/(\d+)"
    match = re.search(pattern, pr_url)
    if match:
        return match.group(1), int(match.group(2))
    # shorthand: owner/repo#123
    short = re.match(r"([^/]+/[^#]+)#(\d+)", pr_url)
    if short:
        return short.group(1), int(short.group(2))
    raise ValueError(f"Cannot parse PR URL: {pr_url!r}")


class GitHubClient:
    """
    Thin, injectable wrapper around PyGithub + raw httpx for diff fetching.
    Constructed once and re-used across the graph execution lifetime.
    """

    def __init__(self,token:Optional[str] = None) -> None:
        settings = get_settings()
        self._token =token or settings.github_token
        if not self._token:
            raise ValueError("No GitHub token provided and no default found in settings.")
        self._gh = Github(self._token)
        self._http = httpx.Client(
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github.v3.diff",   # ← token-efficient diff
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type((GithubException, httpx.HTTPError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def fetch_pr_metadata(self, pr_url: str) -> PRMetadata:
        """Fetch rich PR metadata from GitHub REST API."""
        repo_name, pr_number = _parse_pr_url(pr_url)
        log.info("fetching_pr_metadata", repo=repo_name, pr=pr_number)

        repo = self._gh.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        files_changed = [f.filename for f in pr.get_files()]

        return PRMetadata(
            repo_full_name=repo_name,
            pr_number=pr_number,
            title=pr.title,
            author=pr.user.login,
            base_branch=pr.base.ref,
            head_branch=pr.head.ref,
            files_changed=files_changed,
            additions=pr.additions,
            deletions=pr.deletions,
            pr_body=pr.body or "",
            labels=[label.name for label in pr.labels],
        )

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def fetch_diff(self, pr_url: str) -> str:
        """
        Fetch the unified diff using the GitHub diff media type.
        This is dramatically more token-efficient than fetching full file content.
        """
        repo_name, pr_number = _parse_pr_url(pr_url)
        api_url = f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}"
        log.info("fetching_diff", repo=repo_name, pr=pr_number)

        response = self._http.get(api_url)
        response.raise_for_status()
        return response.text

    def chunk_diff(self, diff: str, max_lines: int) -> List[str]:
        """
        Split a large diff into chunks of ≤ max_lines lines.
        Preserves file boundaries where possible.
        """
        if not diff:
            return []

        lines = diff.splitlines()
        if len(lines) <= max_lines:
            return [diff]

        chunks: List[str] = []
        current: List[str] = []
        count = 0

        for line in lines:
            if line.startswith("diff --git") and count >= max_lines:
                chunks.append("\n".join(current))
                current = [line]
                count = 1
            else:
                current.append(line)
                count += 1

        if current:
            chunks.append("\n".join(current))

        log.info("diff_chunked", total_chunks=len(chunks), original_lines=len(lines))
        return chunks

    @retry(
        retry=retry_if_exception_type((GithubException, httpx.HTTPError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def post_review_comment(
        self,
        pr_url: str,
        body: str,
        comment_id: Optional[int] = None,
    ) -> int:
        """
        Post (or update) the aggregated review as a PR comment.
        Returns the comment ID for future updates.
        """
        repo_name, pr_number = _parse_pr_url(pr_url)
        repo = self._gh.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        if comment_id:
            # Update the existing bot comment instead of creating a new one
            comment = repo.get_issue(pr_number).get_comment(comment_id)
            comment.edit(body)
            log.info("updated_pr_comment", comment_id=comment_id)
            return comment_id
        else:
            issue = repo.get_issue(pr_number)
            comment = issue.create_comment(body)
            log.info("created_pr_comment", comment_id=comment.id)
            return comment.id

    def set_pr_label(self, pr_url: str, label: str) -> None:
        """Add a label to the PR (e.g. 'needs-security-review')."""
        repo_name, pr_number = _parse_pr_url(pr_url)
        repo = self._gh.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        pr.add_to_labels(label)
        log.info("label_added", label=label)

    def close(self) -> None:
        self._http.close()


# ── Singleton accessor ────────────────────────────────────────────────────────

_client: Optional[GitHubClient] = None


def get_github_client(token: str = None) -> GitHubClient:
    #"""Return a module-level singleton GitHub client."""
    #active_token = token or os.getenv("GITHUB_TOKEN")
    #global _client
    #if _client is None:
    #    _client = GitHubClient()
    #return _client
    """
    Return a GitHub client securely initialized with the provided token.
    A new instance is created per call to prevent cross-user token leakage.
    """
    return GitHubClient(token=token)
