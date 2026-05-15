"""
tools/web_search.py — Tavily-powered web search for CRAG's "corrective" step.

When the internal vector store returns low-relevance documents, CRAG falls back
to a targeted web search for current best practices.
"""

from __future__ import annotations

from typing import List

from tavily import TavilyClient

from config import get_settings
from utils.logger import get_logger

log = get_logger("web_search")

# Curated search domains for engineering best practices
_TRUSTED_DOMAINS = [
    "owasp.org",
    "martinfowler.com",
    "refactoring.guru",
    "docs.python.org",
    "portswigger.net",
    "cwe.mitre.org",
    "cheatsheetseries.owasp.org",
]


class WebSearchTool:
    """Wraps Tavily for CRAG web-search fallback."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = TavilyClient(api_key=settings.tavily_api_key)

    def search(self, query: str, max_results: int = 4) -> List[dict]:
        """
        Run a focused web search and return structured results.

        Returns:
            List of dicts with keys: url, title, content, score
        """
        log.info("web_search_triggered", query=query[:80], max_results=max_results)
        try:
            response = self._client.search(
                query=query,
                search_depth="advanced",
                include_domains=_TRUSTED_DOMAINS,
                max_results=max_results,
                include_answer=True,
            )
            results = response.get("results", [])
            log.info("web_search_completed", results_count=len(results))
            return results
        except Exception as exc:
            log.error("web_search_failed", error=str(exc))
            return []

    def get_answer(self, query: str) -> str:
        """Return Tavily's synthesised answer string for a query."""
        try:
            response = self._client.search(
                query=query,
                search_depth="advanced",
                include_domains=_TRUSTED_DOMAINS,
                max_results=3,
                include_answer=True,
            )
            return response.get("answer", "")
        except Exception as exc:
            log.error("web_answer_failed", error=str(exc))
            return ""


# ── Singleton ─────────────────────────────────────────────────────────────────

_tool: WebSearchTool | None = None


def get_web_search_tool() -> WebSearchTool:
    global _tool
    if _tool is None:
        _tool = WebSearchTool()
    return _tool
