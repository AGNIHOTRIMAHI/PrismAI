"""
graph.py — LangGraph Multi-Agent PR Reviewer Workflow

Topology (ASCII):
                         ┌─────────────┐
                         │   fetcher   │  ← GitHub diff + metadata
                         └──────┬──────┘
                                │
                         ┌──────▼──────┐
                         │  crag_node  │  ← RAG enrichment / web search
                         └──────┬──────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
     ┌──────▼──────┐   ┌───────▼──────┐   ┌───────▼──────┐
     │  security   │   │ performance  │   │    style     │
     │    agent    │   │    agent     │   │    agent     │
     └──────┬──────┘   └──────┬───────┘   └──────┬───────┘
            │                  │                  │
            └──────────────────┼──────────────────┘
                               │  (fan-in via Annotated[List, add])
                        ┌──────▼──────┐
                        │ aggregator  │  ← synthesise + post GitHub comment
                        └──────┬──────┘
                               │
                    ┌──────────▼───────────┐
                    │  hitl required?      │
                    │  (conditional edge)  │
                    └────┬─────────────────┘
                         │ YES            │ NO
                  ┌──────▼──────┐    ┌────▼─────┐
                  │ hitl_notify │    │   END    │
                  └──────┬──────┘    └──────────┘
                         │ (INTERRUPT — graph pauses)
                  ┌──────▼──────┐
                  │ hitl_resume │  ← human sends decision via API
                  └──────┬──────┘
                         │
                      ┌──▼───┐
                      │  END │
                      └──────┘

Key LangGraph patterns used:
  • StateGraph with TypedDict state
  • add_node / add_edge / add_conditional_edges
  • Parallel fan-out via Send (concurrent specialist agents)
  • interrupt() for HITL pause-and-resume
  • MemorySaver checkpointer for state persistence
"""
from __future__ import annotations

from typing import Literal
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver


#from langgraph.checkpoint.memory import MemorySaver
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
    Each Send creates a concurrent branch of the graph.
    LangGraph merges their outputs via the `Annotated[List, add]` fields.
    """
    return [
        Send("security_agent",    state),
        Send("performance_agent", state),
        Send("style_agent",       state),
    ]


def route_after_aggregation(
    state: PRReviewState,
) -> Literal["hitl_notify_node", "__end__"]:
    """
    Conditional edge: if the security score breaches the threshold,
    route to HITL; otherwise finish.
    """
    if state.get("hitl_required"):
        log.info("routing_to_hitl", security_score=state.get("security_score"))
        return "hitl_notify_node"
    log.info("routing_to_end", security_score=state.get("security_score"))
    return END


def route_after_hitl_notify(state: PRReviewState) -> Literal["hitl_resume_node"]:
    """
    After notifying the human, the graph INTERRUPTS here.
    When resumed, it always goes to hitl_resume_node.
    """
    # This interrupt() call pauses the graph and surfaces to the caller.
    # The FastAPI /hitl/respond endpoint injects hitl_decision into state
    # and calls graph.invoke() again to resume from this point.
    interrupt("Waiting for human reviewer decision…")
    return "hitl_resume_node"


# ══════════════════════════════════════════════════════════════════════════════
# Graph Builder
# ══════════════════════════════════════════════════════════════════════════════

def build_graph() -> "CompiledStateGraph":
    """
    Construct and compile the full multi-agent LangGraph workflow.

    Returns a compiled graph ready to be invoked with an initial state dict.
    """
    log.info("building_langgraph")
    builder = StateGraph(PRReviewState)

    # ── Register nodes ────────────────────────────────────────────────────────
    builder.add_node("fetcher",            fetcher_node)
    builder.add_node("crag_node",          crag_node)
    builder.add_node("security_agent",     security_agent_node)
    builder.add_node("performance_agent",  performance_agent_node)
    builder.add_node("style_agent",        style_agent_node)
    builder.add_node("aggregator",         aggregator_node)
    builder.add_node("hitl_notify_node",   hitl_notify_node)
    builder.add_node("hitl_resume_node",   hitl_resume_node)

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
        # Each branch can go to its specialist node
        ["security_agent", "performance_agent", "style_agent"],
    )

    # All three specialists → aggregator (LangGraph auto-waits for all parallel branches)
    builder.add_edge("security_agent",    "aggregator")
    builder.add_edge("performance_agent", "aggregator")
    builder.add_edge("style_agent",       "aggregator")

    # aggregator → HITL or END
    builder.add_conditional_edges(
        "aggregator",
        route_after_aggregation,
        {"hitl_notify_node": "hitl_notify_node", END: END},
    )

    # HITL flow (interrupt-and-resume)
    builder.add_conditional_edges(
        "hitl_notify_node",
        route_after_hitl_notify,
        {"hitl_resume_node": "hitl_resume_node"},
    )
    builder.add_edge("hitl_resume_node", END)

    # ── Compile with memory checkpointer ──────────────────────────────────────
    # MemorySaver persists state across interrupt/resume.
    # In production, swap for SqliteSaver or RedisSaver for durability.
    #checkpointer = MemorySaver()
    #compiled = builder.compile(checkpointer=checkpointer)

    #log.info("langgraph_compiled_successfully")
    #return compiled
    # ── Compile with PERSISTENT SQLite Checkpointer ───────────────────────────
    # The 'check_same_thread=False' argument is vital when deploying to 
    # servers like FastAPI/Render, which handle multiple threads.
    conn = sqlite3.connect("prism_memory.sqlite", check_same_thread=False)
    
    # Initialize the SqliteSaver with our database connection
    memory = SqliteSaver(conn)
    memory.setup()
    compiled = builder.compile(checkpointer=memory)

    log.info("langgraph_compiled_successfully_with_sqlite_persistence")
    return compiled

# ── Module-level singleton ────────────────────────────────────────────────────
# Built once on import; shared across all FastAPI request handlers.
pr_review_graph = build_graph()
