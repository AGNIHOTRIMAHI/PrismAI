"""
graph.py — LangGraph Multi-Agent PR Reviewer Workflow
"""
from __future__ import annotations

from typing import Literal
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.constants import Send
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt
from langgraph.graph.state import CompiledStateGraph
from agents import (
    aggregator_node,
    crag_node,
    fetcher_node,
    hitl_notify_node,
    hitl_resume_node,
    performance_agent_node,
    security_agent_node,
    style_agent_node,
)
from state import PRReviewState
from utils.logger import get_logger

log = get_logger("graph_builder")


# ══════════════════════════════════════════════════════════════════════════════
# Conditional Edge Functions
# ══════════════════════════════════════════════════════════════════════════════

def route_after_fetch(state: PRReviewState) -> Literal["crag_node", "__end__"]:
    """Stop early if the fetcher failed (e.g. invalid PR URL)."""
    if state.get("error"):
        log.warning("routing_to_end_due_to_error", error=state["error"])
        return END
    return "crag_node"


def fan_out_to_specialists(state: PRReviewState) -> list[Send]:
    """
    Fan-out: dispatch all three specialist agents IN PARALLEL using Send.
    """
    return [
        Send("security_agent",    state),
        Send("performance_agent", state),
        Send("style_agent",       state),
    ]


def route_after_aggregation(
    state: PRReviewState,
) -> Literal["hitl_notify_node", "__end__"]:
    """Route to HITL if required, otherwise finish."""
    if state.get("hitl_required"):
        log.info("routing_to_hitl", security_score=state.get("security_score"))
        return "hitl_notify_node"
    log.info("routing_to_end", security_score=state.get("security_score"))
    return END


# ══════════════════════════════════════════════════════════════════════════════
# HITL Interrupt Node  ← FIX: interrupt() must live inside a NODE, not a router
# ══════════════════════════════════════════════════════════════════════════════

def human_review_interrupt_node(state: PRReviewState) -> PRReviewState:
    """
    Dedicated node that pauses the graph for human review.

    interrupt() is only valid inside a node function — NOT inside a
    conditional edge / router function. Calling it in a router causes
    KeyError: '__pregel_scratchpad'.

    LangGraph will pause here and surface control to the caller.
    The FastAPI /approve endpoint calls graph.update_state() + graph.invoke()
    to resume from this checkpoint.
    """
    interrupt("Waiting for human reviewer decision…")
    return state  # resumed: pass state through to hitl_resume_node


# ══════════════════════════════════════════════════════════════════════════════
# Graph Builder
# ══════════════════════════════════════════════════════════════════════════════

def build_graph() -> "CompiledStateGraph":
    """
    Construct and compile the full multi-agent LangGraph workflow.
    """
    log.info("building_langgraph")
    builder = StateGraph(PRReviewState)

    # ── Register nodes ────────────────────────────────────────────────────────
    builder.add_node("fetcher",                    fetcher_node)
    builder.add_node("crag_node",                  crag_node)
    builder.add_node("security_agent",             security_agent_node)
    builder.add_node("performance_agent",          performance_agent_node)
    builder.add_node("style_agent",                style_agent_node)
    builder.add_node("aggregator",                 aggregator_node)
    builder.add_node("hitl_notify_node",           hitl_notify_node)
    builder.add_node("human_review_interrupt",     human_review_interrupt_node)  # ← NEW
    builder.add_node("hitl_resume_node",           hitl_resume_node)

    # ── Set entry point ───────────────────────────────────────────────────────
    builder.set_entry_point("fetcher")

    # ── Edges ─────────────────────────────────────────────────────────────────

    # fetcher → (crag or END on error)
    builder.add_conditional_edges(
        "fetcher",
        route_after_fetch,
        {"crag_node": "crag_node", END: END},
    )

    # crag → fan-out to all three specialists IN PARALLEL
    builder.add_conditional_edges(
        "crag_node",
        fan_out_to_specialists,
        ["security_agent", "performance_agent", "style_agent"],
    )

    # All three specialists → aggregator
    builder.add_edge("security_agent",    "aggregator")
    builder.add_edge("performance_agent", "aggregator")
    builder.add_edge("style_agent",       "aggregator")

    # aggregator → HITL or END
    builder.add_conditional_edges(
        "aggregator",
        route_after_aggregation,
        {"hitl_notify_node": "hitl_notify_node", END: END},
    )

    # HITL flow:
    #   hitl_notify_node → human_review_interrupt (pauses here) → hitl_resume_node → END
    builder.add_edge("hitl_notify_node",       "human_review_interrupt")  # ← was a conditional edge before
    builder.add_edge("human_review_interrupt", "hitl_resume_node")        # resumes after interrupt
    builder.add_edge("hitl_resume_node",       END)

    # ── Compile with SQLite checkpointer ─────────────────────────────────────
    conn = sqlite3.connect("prism_memory.sqlite", check_same_thread=False)
    memory = SqliteSaver(conn)
    memory.setup()
    compiled = builder.compile(checkpointer=memory, interrupt_before=["human_review_interrupt"])

    log.info("langgraph_compiled_successfully_with_sqlite_persistence")
    return compiled


# ── Module-level singleton ────────────────────────────────────────────────────
pr_review_graph = build_graph()