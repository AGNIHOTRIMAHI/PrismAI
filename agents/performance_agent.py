"""
agents/performance_agent.py — Performance Specialist Node

Detects algorithm complexity issues, N+1 query patterns, unbounded data loads,
memory leaks, and missing caching opportunities using Gemini.

Runs in PARALLEL with security_agent and style_agent.
"""

from __future__ import annotations

import re
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI

from config import get_settings
from prompts import PERFORMANCE_PROMPT
from state import Finding, PRReviewState
from utils.logger import get_logger

import os
GOOGLE_API_KEY_PERFORMANCE = os.getenv("GOOGLE_API_KEY_PERFORMANCE") or os.getenv("GOOGLE_API_KEY")



log = get_logger("performance_agent")

_PERF_PATTERNS = [
    (r"for\s+\w+\s+in\s+.+:\n\s+.*(query|filter|get|fetch|find)\(", "Possible N+1 query inside loop"),
    (r"SELECT\s+\*\s+FROM", "SELECT * — fetch only needed columns"),
    (r"time\.sleep\(\d+\)", "Blocking sleep in request path"),
    (r"\.all\(\)\s*$", "Unbounded .all() — consider pagination"),
]


def _quick_perf_scan(diff: str) -> list[tuple[str, str]]:
    hits = []
    for pattern, description in _PERF_PATTERNS:
        for match in re.finditer(pattern, diff, re.MULTILINE):
            hits.append((match.group()[:80].strip(), description))
    return hits


def _extract_performance_score(report: str) -> int:
    match = re.search(r"Performance Score[:\s]+(\d+)/10", report, re.IGNORECASE)
    return min(10, max(0, int(match.group(1)))) if match else 0


def performance_agent_node(state: PRReviewState) -> PRReviewState:
    """
    LangGraph Node: Performance specialist agent using Gemini.
    """
    settings = get_settings()
    log.info("performance_agent_started")

    meta = state.get("pr_metadata", {})
    diff = state.get("diff_context", "")
    crag_context = state.get("crag_enhanced_context", "No additional context available.")

    # ── Heuristic Pre-scan ────────────────────────────────────────────────────
    perf_hits = _quick_perf_scan(diff)
    pre_scan_note = ""
    pre_scan_findings: list[Finding] = []

    if perf_hits:
        pre_scan_note = "\n⚠️ **Pre-scan detected potential performance issues:**\n"
        for matched, description in perf_hits:
            pre_scan_note += f"  - {description}: `{matched}…`\n"
            pre_scan_findings.append(
                Finding(
                    agent="performance",
                    severity="medium",
                    category="Performance Anti-Pattern",
                    file="[detected in diff]",
                    line=None,
                    message=f"{description}: {matched[:50]}…",
                    suggestion="Review loop structure and database access patterns.",
                )
            )
        log.warning("perf_patterns_detected", count=len(perf_hits))

    # ── LLM Deep Analysis (Gemini) ────────────────────────────────────────────
    llm = ChatGoogleGenerativeAI(
        model=settings.google_model,
        google_api_key=GOOGLE_API_KEY_PERFORMANCE,
        temperature=settings.google_temperature,
    )

    chain = PERFORMANCE_PROMPT | llm
    response = chain.invoke(
        {
            "crag_context": crag_context,
            "pr_title": meta.get("title", "N/A"),
            "pr_author": meta.get("author", "N/A"),
            "files_changed": ", ".join(meta.get("files_changed", [])[:10]),
            "diff_context": diff[:8000],
        }
    )

    llm_report: str = response.content
    if pre_scan_note:
        llm_report = pre_scan_note + "\n---\n" + llm_report

    performance_score = _extract_performance_score(llm_report)
    log.info("performance_analysis_complete", score=performance_score)

    return {
       
        "performance_report": llm_report,
        "findings": pre_scan_findings,
        "node_execution_log": [
            f"[{datetime.utcnow().isoformat()}] performance_agent: "
            f"score={performance_score}/10, prescan_hits={len(perf_hits)}"
        ],
    }
