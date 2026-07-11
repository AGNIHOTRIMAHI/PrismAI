"""
agents/crag_node.py — Corrective RAG (CRAG) Node

Enriches review context BEFORE specialist agents run using Gemini.

Algorithm:
  1. Build a semantic query from PR metadata + diff summary.
  2. Retrieve top-k documents from the internal vector store.
  3. Grade each document for relevance (LLM-as-judge via Gemini).
  4. If average relevance < threshold → trigger Tavily web search.
  5. Distil retrieved knowledge into compact context for specialist agents.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import List

from langchain_google_genai import ChatGoogleGenerativeAI

from config import get_settings
from prompts import CRAG_GRADER_PROMPT
from state import PRReviewState, RAGDocument
from tools.vector_store import get_knowledge_base
from tools.web_search import get_web_search_tool
from utils.logger import get_logger

import os
GOOGLE_API_KEY_CRAG = os.getenv("GOOGLE_API_KEY_CRAG") or os.getenv("GOOGLE_API_KEY")

log = get_logger("crag_node")

_RELEVANCE_THRESHOLD = 0.55
_TOP_K_DOCS = 4


def _build_rag_query(state: PRReviewState) -> str:
    meta = state.get("pr_metadata", {})
    files = ", ".join(meta.get("files_changed", [])[:5])
    diff_head = state.get("diff_context", "")[:500]
    return (
        f"PR: {meta.get('title', 'Unknown')}. "
        f"Files changed: {files}. "
        f"Diff excerpt: {diff_head}"
    )


def _grade_document(
    llm: ChatGoogleGenerativeAI, query: str, doc_content: str
) -> float:
    try:
        chain = CRAG_GRADER_PROMPT | llm
        response = chain.invoke({"query": query, "document": doc_content[:800]})
        raw = response.content.strip()
        # Gemini sometimes wraps JSON in markdown fences — strip them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw.strip())
        score = float(parsed.get("score", 0.0))
        return max(0.0, min(1.0, score))
    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        log.warning("grading_parse_failed", error=str(exc))
        return 0.0


def crag_node(state: PRReviewState) -> PRReviewState:
    """
    LangGraph Node: Corrective RAG — enrich review context with relevant knowledge.
    """
    settings = get_settings()
    log.info("crag_node_started")

    llm = ChatGoogleGenerativeAI(
        model=settings.google_model,
        google_api_key=GOOGLE_API_KEY_CRAG,
        temperature=0.0,  # deterministic grading
    )

    query = _build_rag_query(state)
    log.debug("rag_query", query=query[:100])

    kb = get_knowledge_base()
    raw_results = kb.similarity_search_with_score(query, k=_TOP_K_DOCS)

    retrieved_docs: List[RAGDocument] = []
    relevance_scores: List[float] = []

    for doc, vector_score in raw_results:
        llm_score = _grade_document(llm, query, doc.page_content)
        blended_score = 0.5 * vector_score + 0.5 * llm_score
        relevance_scores.append(blended_score)
        retrieved_docs.append(
            RAGDocument(
                source=doc.metadata.get("source", "internal"),
                content=doc.page_content,
                relevance_score=float(blended_score),
                is_web_sourced=False,
            )
        )
        log.debug(
            "doc_graded",
            source=doc.metadata.get("source", ""),
            vector_score=round(vector_score, 3),
            llm_score=round(llm_score, 3),
            blended=round(blended_score, 3),
        )

    avg_relevance = (
        sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
    )
    triggered_web_search = False

    if avg_relevance < _RELEVANCE_THRESHOLD:
        log.info(
            "low_relevance_triggering_web_search",
            avg_relevance=round(avg_relevance, 3),
        )
        triggered_web_search = True
        searcher = get_web_search_tool()
        web_results = searcher.search(
            query=f"code review best practices {query[:120]}",
            max_results=3,
        )
        for result in web_results:
            retrieved_docs.append(
                RAGDocument(
                    source=result.get("url", "web"),
                    content=result.get("content", ""),
                    relevance_score=result.get("score", 0.5),
                    is_web_sourced=True,
                )
            )

    top_docs = sorted(
        retrieved_docs, key=lambda d: d["relevance_score"], reverse=True
    )[:3]
    crag_context = "\n\n---\n".join(
        f"[Source: {d['source']}]\n{d['content'][:600]}" for d in top_docs
    )

    log.info(
        "crag_node_completed",
        docs_retrieved=len(retrieved_docs),
        avg_relevance=round(avg_relevance, 3),
        web_search_triggered=triggered_web_search,
    )

    return {
        **state,
        "retrieved_docs": retrieved_docs,
        "crag_relevance_score": float(avg_relevance),
        "crag_triggered_web_search": triggered_web_search,
        "crag_enhanced_context": crag_context,
        "node_execution_log": [
            f"[{datetime.utcnow().isoformat()}] crag_node: "
            f"avg_relevance={avg_relevance:.2f}, "
            f"web_search={'YES' if triggered_web_search else 'NO'}, "
            f"docs={len(retrieved_docs)}"
        ],
    }
