"""
agents/fetcher.py — Fetcher Node

Responsibilities:
  1. Parse PR URL → extract repo + PR number
  2. Call GitHub API for metadata (title, author, files, etc.)
  3. Fetch raw unified diff (token-efficient format)
  4. Chunk the diff if it exceeds MAX_DIFF_LINES
  5. Update shared state and continue the graph
"""

from __future__ import annotations

from datetime import datetime

from config import get_settings
from state import PRReviewState
from tools.github_tools import get_github_client
from utils.logger import get_logger

log = get_logger("fetcher_node")


def fetcher_node(state: PRReviewState) -> PRReviewState:
    """
    LangGraph Node: Fetch PR metadata and diff from GitHub.

    Entry point of the review pipeline. All downstream nodes depend on the
    `diff_context` and `pr_metadata` fields populated here.
    """
    settings = get_settings()
    pr_url = state["pr_url"]
    user_token = state.get("github_token")
    log.info("fetcher_started", pr_url=pr_url, using_custom_token=bool(user_token))

    try:
        client = get_github_client(token=user_token)

        # ── Step 1: Metadata ─────────────────────────────────────────────────
        metadata = client.fetch_pr_metadata(pr_url)
        log.info(
            "metadata_fetched",
            repo=metadata["repo_full_name"],
            pr=metadata["pr_number"],
            author=metadata["author"],
            files=len(metadata["files_changed"]),
        )

        # ── Step 2: Diff ─────────────────────────────────────────────────────
        diff = client.fetch_diff(pr_url)
        diff_lines = diff.count("\n")
        log.info("diff_fetched", lines=diff_lines)

        # ── Step 3: Chunking (for large PRs) ─────────────────────────────────
        diff_chunks = client.chunk_diff(diff, max_lines=settings.max_diff_lines)

        # For small diffs, diff_context is the full diff; for large ones it's
        # the first chunk (other chunks are available via diff_chunks).
        primary_diff = diff_chunks[0] if diff_chunks else diff

        return {
            #**state,
            "pr_metadata": metadata,
            "diff_context": primary_diff,
            "diff_chunks": diff_chunks,
            "node_execution_log": [
                f"[{datetime.utcnow().isoformat()}] fetcher_node: OK — "
                f"{diff_lines} diff lines, {len(diff_chunks)} chunks"
            ],
        }

    except Exception as exc:
        log.error("fetcher_failed", error=str(exc), pr_url=pr_url)
        return {
            #**state,
            "error": f"Fetcher failed: {exc}",
            "node_execution_log": [
                f"[{datetime.utcnow().isoformat()}] fetcher_node: ERROR — {exc}"
            ],
        }
