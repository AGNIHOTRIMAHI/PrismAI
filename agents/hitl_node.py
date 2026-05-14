"""
agents/hitl_node.py — Human-in-the-Loop (HITL) Node

This node implements LangGraph's interrupt-and-resume pattern for human oversight.

Flow:
  1. `hitl_notify_node` — sends an alert to the configured channel (Slack/email/console)
     and marks `awaiting_human = True`. LangGraph then INTERRUPTS the graph.
  2. A human reviewer submits their decision via the FastAPI `/hitl/respond` endpoint.
  3. `hitl_resume_node` — processes the decision: APPROVE, REQUEST_CHANGES, or ESCALATE.

This is a "breakpoint" in LangGraph terminology — the graph pauses at a defined
interrupt point and waits for external input before resuming.
"""

from __future__ import annotations

from datetime import datetime, timezone

from langchain_core.runnables import RunnableConfig

from config import get_settings
from state import HITLDecision, PRReviewState
from utils.logger import get_logger

log = get_logger("hitl_node")


# ══════════════════════════════════════════════════════════════════════════════
# Notification helpers (channel-specific)
# ══════════════════════════════════════════════════════════════════════════════

def _notify_console(state: PRReviewState) -> None:
    """Development: print to console for manual inspection."""
    meta = state.get("pr_metadata", {})
    print("\n" + "=" * 70)
    print("⚠️  HUMAN REVIEW REQUIRED")
    print("=" * 70)
    print(f"  PR     : {state['pr_url']}")
    print(f"  Title  : {meta.get('title', 'N/A')}")
    print(f"  Author : @{meta.get('author', 'N/A')}")
    print(f"  Score  : {state.get('security_score', 0)}/10 (BLOCKED)")
    print("─" * 70)
    print("  POST to /hitl/respond with body:")
    print('  {"pr_url": "<url>", "reviewer": "<name>",')
    print('   "decision": "approve|request_changes|escalate", "comment": "…"}')
    print("=" * 70 + "\n")


def _notify_slack(state: PRReviewState) -> None:
    """Production: post a rich Slack message with action buttons."""
    try:
        import httpx
        settings = get_settings()
        meta = state.get("pr_metadata", {})
        payload = {
            "channel": settings.slack_review_channel_id,
            "text": f"⚠️ PR Security Review Required — {state['pr_url']}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*⚠️ High-Severity PR Flagged for Human Review*\n"
                            f"*PR:* <{state['pr_url']}|{meta.get('title', 'N/A')}>\n"
                            f"*Author:* @{meta.get('author', 'N/A')}\n"
                            f"*Security Score:* {state.get('security_score', 0)}/10\n"
                        ),
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ Approve"},
                            "style": "primary",
                            "value": f"approve|{state['pr_url']}",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "🔄 Request Changes"},
                            "value": f"request_changes|{state['pr_url']}",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "🚨 Escalate"},
                            "style": "danger",
                            "value": f"escalate|{state['pr_url']}",
                        },
                    ],
                },
            ],
        }
        with httpx.Client(timeout=10.0) as client:
            client.post(
                "https://slack.com/api/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {settings.slack_bot_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        log.info("slack_notification_sent", channel=settings.slack_review_channel_id)
    except Exception as exc:
        log.error("slack_notification_failed", error=str(exc))
        _notify_console(state)   # Fallback to console


def _send_hitl_notification(state: PRReviewState) -> None:
    settings = get_settings()
    channel = settings.hitl_notification_channel
    dispatch = {"slack": _notify_slack, "console": _notify_console}
    dispatch.get(channel, _notify_console)(state)


# ══════════════════════════════════════════════════════════════════════════════
# LangGraph Nodes
# ══════════════════════════════════════════════════════════════════════════════

def hitl_notify_node(state: PRReviewState) -> PRReviewState:
    """
    LangGraph Node: Send HITL notification.

    After this node, the graph hits an `interrupt()` call — execution pauses
    and control returns to the caller (FastAPI). State is persisted in the
    LangGraph checkpointer so it can be resumed later.
    """
    log.info("hitl_notify_started", security_score=state.get("security_score"))
    _send_hitl_notification(state)

    return {
        **state,
        "awaiting_human": True,
        "node_execution_log": [
            f"[{datetime.utcnow().isoformat()}] hitl_notify_node: "
            f"notification_sent, awaiting_human=True"
        ],
    }


def hitl_resume_node(state: PRReviewState) -> PRReviewState:
    """
    LangGraph Node: Process the human decision after graph is resumed.

    Called by graph.invoke() after the interrupt is resolved via the API.
    The `hitl_decision` field will have been injected into state by the
    /hitl/respond endpoint before resume.
    """
    decision: HITLDecision | None = state.get("hitl_decision")
    log.info(
        "hitl_resume_started",
        decision=decision.get("decision") if decision else "missing",
    )

    if not decision:
        log.warning("hitl_no_decision_found")
        return {
            **state,
            "awaiting_human": False,
            "is_ready_for_merge": False,
            "node_execution_log": [
                f"[{datetime.utcnow().isoformat()}] hitl_resume_node: WARNING — no decision found"
            ],
        }

    choice = decision["decision"]
    is_ready = choice == "approve"
    log.info("hitl_decision_processed", decision=choice, reviewer=decision.get("reviewer"))

    return {
        **state,
        "awaiting_human": False,
        "is_ready_for_merge": is_ready,
        "node_execution_log": [
            f"[{datetime.utcnow().isoformat()}] hitl_resume_node: "
            f"decision={choice}, reviewer={decision.get('reviewer')}, "
            f"merge_ready={is_ready}"
        ],
    }
