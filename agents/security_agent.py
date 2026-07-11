"""
agents/security_agent.py — Security Specialist Node

Analyses the PR diff for OWASP Top 10 vulnerabilities, hardcoded secrets,
authentication flaws, and other security anti-patterns using Gemini.

Runs in PARALLEL with performance_agent and style_agent.
"""

from __future__ import annotations

import re
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI

from config import get_settings
from prompts import SECURITY_PROMPT
from state import Finding, PRReviewState
from utils.logger import get_logger

import os
GOOGLE_API_KEY_SECURITY = os.getenv("GOOGLE_API_KEY_SECURITY") or os.getenv("GOOGLE_API_KEY")

log = get_logger("security_agent")

_SECRET_PATTERNS = [
    (r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']+["\']', "Hardcoded password"),
    (r'(?i)(api_key|apikey|secret_key)\s*=\s*["\'][^"\']+["\']', "Hardcoded API key"),
    (r'(?i)(aws_access_key_id|aws_secret)\s*=\s*["\'][^"\']+["\']', "Hardcoded AWS key"),
    (r'-----BEGIN\s+(RSA|EC|OPENSSH)\s+PRIVATE KEY-----', "Embedded private key"),
    (r'(?i)Authorization:\s*Bearer\s+[A-Za-z0-9\-_\.]+', "Hardcoded bearer token"),
]


def _quick_secret_scan(diff: str) -> list[tuple[str, str]]:
    hits = []
    for pattern, description in _SECRET_PATTERNS:
        for match in re.finditer(pattern, diff):
            hits.append((match.group()[:60], description))
    return hits


def _extract_security_score(report: str) -> int:
    match = re.search(r"Security Score[:\s]+(\d+)/10", report, re.IGNORECASE)
    if match:
        return min(10, max(0, int(match.group(1))))
    return 0


def security_agent_node(state: PRReviewState) -> PRReviewState:
    """
    LangGraph Node: Security specialist agent using Gemini.
    Combines fast regex pre-scan with deep LLM analysis.
    """
    settings = get_settings()
    log.info("security_agent_started")

    meta = state.get("pr_metadata", {})
    diff = state.get("diff_context", "")
    crag_context = state.get("crag_enhanced_context", "No additional context available.")

    # ── Fast pre-scan ─────────────────────────────────────────────────────────
    secret_hits = _quick_secret_scan(diff)
    pre_scan_note = ""
    pre_scan_findings: list[Finding] = []

    if secret_hits:
        pre_scan_note = "\n⚠️ **Pre-scan detected potential secrets:**\n"
        for matched, description in secret_hits:
            pre_scan_note += f"  - {description}: `{matched}…`\n"
            pre_scan_findings.append(
                Finding(
                    agent="security",
                    severity="critical",
                    category="Secrets Exposure",
                    file="[detected in diff]",
                    line=None,
                    message=f"{description} detected: {matched[:40]}…",
                    suggestion="Move to environment variables or a secrets manager.",
                )
            )
        log.warning("secrets_detected_in_prescan", count=len(secret_hits))

    # ── LLM Deep Analysis (Gemini) ────────────────────────────────────────────
    llm = ChatGoogleGenerativeAI(
        model=settings.google_model,
        google_api_key=GOOGLE_API_KEY_SECURITY,
        temperature=settings.google_temperature,
    )

    chain = SECURITY_PROMPT | llm
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

    security_score = _extract_security_score(llm_report)
    log.info("security_analysis_complete", score=security_score)

    return {
        
        "security_report": llm_report,
        "security_score": security_score,
        "findings": pre_scan_findings,
        "node_execution_log": [
            f"[{datetime.utcnow().isoformat()}] security_agent: "
            f"score={security_score}/10, prescan_hits={len(secret_hits)}"
        ],
    }
