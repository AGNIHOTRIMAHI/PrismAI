"""
agents/aggregator.py — Aggregator Node

After the three specialist agents complete (parallel fan-in), this node:
  1. Receives all three reports from state.
  2. Synthesises them into a structured GitHub-flavoured Markdown comment via Gemini.
  3. Always sets hitl_required = True — every PR requires a human to merge.
  4. Posts the final comment to GitHub.
"""

from __future__ import annotations

from datetime import datetime, timezone

from langchain_google_genai import ChatGoogleGenerativeAI

from config import get_settings
from prompts import AGGREGATOR_PROMPT
from state import PRReviewState
from tools.github_tools import get_github_client
from utils.logger import get_logger

log = get_logger("aggregator_node")

# ── Severity helpers ───────────────────────────────────────────────────────────

_CRITICAL_MARKERS = ("🔴", "Critical")
_HIGH_MARKERS     = ("🟠", "High")


def _compute_verdict(final_report: str) -> tuple[str, bool]:
    """
    Derive a display verdict from the generated report text.
    Human review is always required — this only determines the label shown.

    Returns:
        verdict    — human-readable verdict string for logging and GitHub label
        is_blocked — True when Critical findings exist (hard merge block)
    """
    has_critical = any(m in final_report for m in _CRITICAL_MARKERS)
    has_high     = any(m in final_report for m in _HIGH_MARKERS)

    if has_critical:
        return "BLOCKED ❌", True
    if has_high:
        return "CAUTION ⚠️", False
    return "READY FOR HUMAN REVIEW ✅", False


# ── Node ───────────────────────────────────────────────────────────────────────

def aggregator_node(state: PRReviewState) -> PRReviewState:
    """
    LangGraph Node: Aggregate all specialist reviews into one final PR comment.
    Human-in-the-loop is enforced unconditionally — no PR merges automatically.
    """
    settings = get_settings()
    log.info("aggregator_started")

    meta               = state.get("pr_metadata", {})
    security_report    = state.get("security_report",    "No security review available.")
    performance_report = state.get("performance_report", "No performance review available.")
    style_report       = state.get("style_report",       "No style review available.")
    security_score     = state.get("security_score", 0)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ── LLM Synthesis (Gemini) ─────────────────────────────────────────────────
    llm = ChatGoogleGenerativeAI(
        model=settings.google_model,
        google_api_key=settings.google_api_key,
        temperature=0.1,  # low temp → consistent structured output
    )

    chain = AGGREGATOR_PROMPT | llm
    response = chain.invoke(
        {
            "pr_title":           meta.get("title", "N/A"),
            "pr_author":          meta.get("author", "N/A"),
            "files_changed":      ", ".join(meta.get("files_changed", [])[:10]),
            "additions":          meta.get("additions", 0),
            "deletions":          meta.get("deletions", 0),
            "security_report":    security_report,
            "performance_report": performance_report,
            "style_report":       style_report,
            "security_score":     security_score,
            "timestamp":          timestamp,
        }
    )

    final_report: str = response.content

    # ── Verdict (display only — human review is unconditional) ────────────────
    verdict, is_blocked = _compute_verdict(final_report)
    hitl_required = True   # always — no PR ever merges without a human
    is_ready      = False  # bot never clears a PR for merge on its own

    log.info(
        "aggregation_complete",
        security_score=security_score,
        verdict=verdict,
        is_blocked=is_blocked,
        hitl_required=hitl_required,
    )

    # ── Post to GitHub ─────────────────────────────────────────────────────────
    github_comment_id: int | None = None
    try:
        #client = get_github_client()
        client = get_github_client(token=state.get("github_token"))
        existing_comment_id = state.get("github_comment_id")
        github_comment_id = client.post_review_comment(
            pr_url=state["pr_url"],
            body=final_report,
            comment_id=existing_comment_id,
        )

        # Always apply needs-human-review; upgrade to blocked if Critical found
        label = "blocked-critical-findings" if is_blocked else "needs-human-review"
        client.set_pr_label(state["pr_url"], label)

    except Exception as exc:
        log.error("github_post_failed", error=str(exc))

    return {
        **state,
        "final_report_markdown": final_report,
        "is_ready_for_merge":    is_ready,
        "hitl_required":         hitl_required,
        "merge_verdict":         verdict,
        "github_comment_id":     github_comment_id,
        "node_execution_log": [
            f"[{timestamp}] aggregator_node: "
            f"verdict={verdict}, "
            f"hitl_required={hitl_required}, "
            f"is_blocked={is_blocked}, "
            f"comment_id={github_comment_id}"
        ],
    }
