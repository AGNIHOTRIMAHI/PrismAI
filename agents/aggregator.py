"""
agents/aggregator.py — Aggregator Node

After the three specialist agents complete (parallel fan-in), this node:
  1. Receives all three reports from state.
  2. Synthesises them into a single GitHub-flavoured Markdown comment via Gemini.
  3. Computes merge readiness.
  4. Sets hitl_required = True if security_score >= threshold.
  5. Posts the final comment to GitHub.
"""

from __future__ import annotations

from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI

from config import get_settings
from prompts import AGGREGATOR_PROMPT
from state import PRReviewState
from tools.github_tools import get_github_client
from utils.logger import get_logger

log = get_logger("aggregator_node")


def aggregator_node(state: PRReviewState) -> PRReviewState:
    """
    LangGraph Node: Aggregate all specialist reviews into one final PR comment.
    """
    settings = get_settings()
    log.info("aggregator_started")

    meta = state.get("pr_metadata", {})
    security_report = state.get("security_report", "No security review available.")
    performance_report = state.get("performance_report", "No performance review available.")
    style_report = state.get("style_report", "No style review available.")
    security_score = state.get("security_score", 0)

    # ── LLM Synthesis (Gemini) ─────────────────────────────────────────────────
    llm = ChatGoogleGenerativeAI(
        model=settings.google_model,
        google_api_key=settings.google_api_key,
        temperature=0.2,  # slight creativity for readable prose
    )

    chain = AGGREGATOR_PROMPT | llm
    response = chain.invoke(
        {
            "pr_title": meta.get("title", "N/A"),
            "pr_author": meta.get("author", "N/A"),
            "files_changed": ", ".join(meta.get("files_changed", [])[:10]),
            "additions": meta.get("additions", 0),
            "deletions": meta.get("deletions", 0),
            "security_report": security_report,
            "performance_report": performance_report,
            "style_report": style_report,
            "security_score": security_score,
        }
    )

    final_report: str = response.content

    # ── Determine merge readiness ─────────────────────────────────────────────
    hitl_required = security_score >= settings.security_block_threshold
    is_ready = security_score < settings.security_block_threshold

    log.info(
        "aggregation_complete",
        security_score=security_score,
        hitl_required=hitl_required,
        is_ready=is_ready,
    )

    # ── Post to GitHub ─────────────────────────────────────────────────────────
    github_comment_id: int | None = None
    try:
        client = get_github_client()
        existing_comment_id = state.get("github_comment_id")
        github_comment_id = client.post_review_comment(
            pr_url=state["pr_url"],
            body=final_report,
            comment_id=existing_comment_id,
        )
        if hitl_required:
            client.set_pr_label(state["pr_url"], "needs-security-review")
    except Exception as exc:
        log.error("github_post_failed", error=str(exc))

    return {
        **state,
        "final_report_markdown": final_report,
        "is_ready_for_merge": is_ready,
        "hitl_required": hitl_required,
        "github_comment_id": github_comment_id,
        "node_execution_log": [
            f"[{datetime.utcnow().isoformat()}] aggregator_node: "
            f"hitl_required={hitl_required}, "
            f"merge_ready={is_ready}, "
            f"comment_id={github_comment_id}"
        ],
    }
