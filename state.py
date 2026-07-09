"""
state.py — The single shared state object that flows through the entire graph.

LangGraph passes this TypedDict between every node. Using `Annotated[List, add]`
for list fields enables safe parallel fan-in (multiple nodes append independently
without overwriting each other).
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, Dict, List, Literal, Optional
from typing_extensions import TypedDict


# ── Sub-structures ────────────────────────────────────────────────────────────

class PRMetadata(TypedDict, total=False):
    """Rich metadata extracted from the GitHub API for a pull request."""
    repo_full_name: str          # "owner/repo"
    pr_number: int
    title: str
    author: str
    base_branch: str
    head_branch: str
    files_changed: List[str]
    additions: int
    deletions: int
    pr_body: str
    labels: List[str]


class Finding(TypedDict):
    """A single issue or suggestion raised by a specialist agent."""
    agent: Literal["security", "performance", "style", "crag"]
    severity: Literal["critical", "high", "medium", "low", "info"]
    category: str
    file: str
    line: Optional[int]
    message: str
    suggestion: str


class RAGDocument(TypedDict):
    """A retrieved document from the vector store or web."""
    source: str         # file path or URL
    content: str
    relevance_score: float
    is_web_sourced: bool


class HITLDecision(TypedDict):
    """Captured human-in-the-loop decision."""
    reviewer: str
    decision: Literal["approve", "request_changes", "escalate"]
    comment: str
    timestamp: str


# ── Primary Graph State ───────────────────────────────────────────────────────

class PRReviewState(TypedDict, total=False):
    """
    The complete state object shared across every node in the LangGraph.

    Design principles:
      - `total=False`      → all fields are optional; nodes only write what they produce.
      - `Annotated[…, add]`→ parallel nodes can safely append without data races.
      - Flat structure     → easier to serialise / checkpoint with LangGraph persistence.
    """

    # ── Input ─────────────────────────────────────────────────────────────────
    pr_url: str     
    github_token: Optional[str]                     # Canonical PR URL
    pr_metadata: PRMetadata              # Structured PR info
    trigger_source: Optional[str] 
    notify_email: Optional[str]
    # ── Fetched Content ───────────────────────────────────────────────────────
    diff_context: str                    # Raw unified diff text
    diff_chunks: List[str]               # Chunked diff for large PRs

    # ── Specialist Reports (parallel nodes write these) ────────────────────────
    security_report: str
    performance_report: str
    style_report: str

    # ── CRAG (Corrective RAG) ─────────────────────────────────────────────────
    retrieved_docs: List[RAGDocument]
    crag_relevance_score: float          # 0.0 – 1.0
    crag_triggered_web_search: bool
    crag_enhanced_context: str           # Distilled knowledge for agents

    # ── Aggregated Findings ───────────────────────────────────────────────────
    # Annotated with `add` → safe parallel fan-in from multiple specialist nodes
    findings: Annotated[List[Finding], add]
    final_report_markdown: str           # The GitHub comment to be posted

    # ── HITL ──────────────────────────────────────────────────────────────────
    hitl_required: bool
    hitl_decision: Optional[HITLDecision]
    awaiting_human: bool                 # Graph is interrupted here

    # ── Control Flow ──────────────────────────────────────────────────────────
    security_score: int                  # 0-10 severity composite
    is_ready_for_merge: bool
    error: Optional[str]                 # Propagated error message
    retry_count: int                     # For node-level retry logic

    # ── Audit / Observability ─────────────────────────────────────────────────
    node_execution_log: Annotated[List[str], add]   # Ordered execution trace
    github_comment_id: Optional[int]     # ID of posted GitHub comment


def initial_state(pr_url: str) -> PRReviewState:
    """Factory: create a clean initial state from a PR URL."""
    return PRReviewState(
        pr_url=pr_url,
        findings=[],
        node_execution_log=[],
        retry_count=0,
        crag_triggered_web_search=False,
        hitl_required=False,
        awaiting_human=False,
        is_ready_for_merge=False,
        security_score=0,
    )
