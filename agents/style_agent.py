"""
agents/style_agent.py — Code Quality & Style Specialist Node

Reviews naming, function size, DRY violations, error handling, type annotations,
dead code, and test coverage gaps using Gemini.

Runs in PARALLEL with security_agent and performance_agent.
"""

from __future__ import annotations

import re
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI

from config import get_settings
from prompts import STYLE_PROMPT
from state import Finding, PRReviewState
from utils.logger import get_logger


import os
GOOGLE_API_KEY_STYLE = os.getenv("GOOGLE_API_KEY_STYLE") or os.getenv("GOOGLE_API_KEY")


log = get_logger("style_agent")

_STYLE_PATTERNS = [
    (r"\bexcept\s*:\s*$", "Bare except clause — silences all errors"),
    (r"\bexcept\s+Exception\s*:\s*\n\s*pass", "Swallowed exception with pass"),
    (r"#\s*TODO|#\s*FIXME|#\s*HACK|#\s*XXX", "Unresolved TODO/FIXME comment"),
    (r"\bprint\s*\(", "print() statement in production code"),
    (r"[0-9]{4,}", "Magic number — use named constant"),
]


def _quick_style_scan(diff: str) -> list[tuple[str, str]]:
    hits = []
    for pattern, description in _STYLE_PATTERNS:
        for match in re.finditer(pattern, diff, re.MULTILINE):
            hits.append((match.group()[:60].strip(), description))
    return hits[:8]


def _extract_quality_score(report: str) -> int:
    match = re.search(r"Quality Score[:\s]+(\d+)/10", report, re.IGNORECASE)
    return min(10, max(0, int(match.group(1)))) if match else 0


def style_agent_node(state: PRReviewState) -> PRReviewState:
    """
    LangGraph Node: Style & code quality specialist agent using Gemini.
    """
    settings = get_settings()
    log.info("style_agent_started")

    meta = state.get("pr_metadata", {})
    diff = state.get("diff_context", "")
    crag_context = state.get("crag_enhanced_context", "No additional context available.")

    # ── Heuristic Pre-scan ────────────────────────────────────────────────────
    style_hits = _quick_style_scan(diff)
    pre_scan_note = ""
    pre_scan_findings: list[Finding] = []

    if style_hits:
        pre_scan_note = "\n⚠️ **Pre-scan detected style issues:**\n"
        for matched, description in style_hits:
            pre_scan_note += f"  - {description}: `{matched}…`\n"
            pre_scan_findings.append(
                Finding(
                    agent="style",
                    severity="low",
                    category="Code Quality",
                    file="[detected in diff]",
                    line=None,
                    message=f"{description}: {matched[:40]}…",
                    suggestion="Follow the project's coding standards and error handling guidelines.",
                )
            )

    # ── LLM Deep Analysis (Gemini) ────────────────────────────────────────────
    llm = ChatGoogleGenerativeAI(
        model=settings.google_model,
        google_api_key=GOOGLE_API_KEY_STYLE,
        temperature=settings.google_temperature,
    )

    chain = STYLE_PROMPT | llm
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

    quality_score = _extract_quality_score(llm_report)
    log.info("style_analysis_complete", score=quality_score)

    return {
        
        "style_report": llm_report,
        "findings": pre_scan_findings,
        "node_execution_log": [
            f"[{datetime.utcnow().isoformat()}] style_agent: "
            f"score={quality_score}/10, prescan_hits={len(style_hits)}"
        ],
    }
