"""
tools/vector_store.py — FAISS-backed vector store using Google Gemini Embeddings.

On first run it indexes all Markdown / text files found under docs/knowledge/.
On subsequent runs it loads the persisted index from disk.

This is the "retrieval" layer of Corrective RAG (CRAG).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import get_settings
from utils.logger import get_logger

log = get_logger("vector_store")

_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=120,
    separators=["\n## ", "\n### ", "\n\n", "\n", " "],
)


class EngineeringKnowledgeBase:
    """
    Wraps a FAISS vector store with engineering best-practice documents.
    Uses Google Gemini Embeddings instead of OpenAI.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._store_path = Path(settings.vector_store_path)
        # ── Gemini Embeddings (replaces OpenAIEmbeddings) ─────────────────────
        self._embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.google_embedding_model,
            google_api_key=settings.google_api_key,
        )
        self._store: Optional[FAISS] = None

    def build_or_load(
        self, docs_dir: str = "./docs/knowledge"
    ) -> "EngineeringKnowledgeBase":
        """
        Load the persisted FAISS index if it exists; otherwise build from docs_dir.
        """
        index_file = self._store_path / "index.faiss"
        if index_file.exists():
            log.info("loading_existing_vector_store", path=str(self._store_path))
            self._store = FAISS.load_local(
                str(self._store_path),
                self._embeddings,
                allow_dangerous_deserialization=True,
            )
        else:
            log.info("building_vector_store", docs_dir=docs_dir)
            self._store = self._build(docs_dir)
        return self

    def _build(self, docs_dir: str) -> FAISS:
        docs_path = Path(docs_dir)
        docs_path.mkdir(parents=True, exist_ok=True)

        if not any(docs_path.iterdir()):
            self._seed_defaults(docs_path)

        loader = DirectoryLoader(
            str(docs_path),
            glob="**/*.{md,txt}",
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
            show_progress=False,
        )
        raw_docs: List[Document] = loader.load()
        if not raw_docs:
            log.warning("no_documents_found", path=str(docs_path))
            raw_docs = [
                Document(
                    page_content="No engineering docs indexed yet.", metadata={}
                )
            ]

        split_docs = _SPLITTER.split_documents(raw_docs)
        store = FAISS.from_documents(split_docs, self._embeddings)
        store.save_local(str(self._store_path))
        log.info("vector_store_built", chunks=len(split_docs))
        return store

    def similarity_search_with_score(
        self, query: str, k: int = 4
    ) -> List[tuple[Document, float]]:
        if self._store is None:
            raise RuntimeError("Vector store not initialised. Call build_or_load() first.")
        results = self._store.similarity_search_with_relevance_scores(query, k=k)
        log.debug("retrieved_docs", query=query[:60], count=len(results))
        return results

    def add_documents(self, texts: List[str], source: str = "manual") -> None:
        if self._store is None:
            raise RuntimeError("Vector store not initialised.")
        docs = [Document(page_content=t, metadata={"source": source}) for t in texts]
        split_docs = _SPLITTER.split_documents(docs)
        self._store.add_documents(split_docs)
        self._store.save_local(str(self._store_path))
        log.info("documents_added", count=len(split_docs))

    @staticmethod
    def _seed_defaults(docs_path: Path) -> None:
        seeds = {
            "owasp_top10.md": """\
# OWASP Top 10 — Quick Reference

## A01 Broken Access Control
Restrict what authenticated users can do. Never trust client-supplied roles.
Always enforce server-side authorisation checks.

## A02 Cryptographic Failures
Use AES-256 for data at rest, TLS 1.2+ for transit. Never MD5/SHA-1 for passwords.
Use bcrypt, argon2id, or scrypt for password hashing.

## A03 Injection
Parametrise ALL database queries. Never concatenate user input into SQL strings.
Apply input validation on every external input boundary.

## A07 Identification & Authentication Failures
Implement MFA. Use short-lived JWTs. Rotate secrets regularly.

## A09 Security Logging & Monitoring Failures
Log all authentication events, privilege changes, and exceptions.
""",
            "clean_code.md": """\
# Clean Code Principles

## Meaningful Names
Variable names should reveal intent. `elapsed_time_in_days` beats `d`.

## Functions
Functions should do ONE thing. Ideal length: fewer than 20 lines. Max arguments: 3.

## DRY
Duplicate logic is a maintenance time-bomb. Extract shared logic into helpers.

## Error Handling
Prefer exceptions to error codes. Never swallow exceptions silently.

## Comments
Code should be self-documenting. Comments explain *why*, not *what*.
""",
            "performance_patterns.md": """\
# Performance Best Practices

## Algorithm Complexity
Prefer O(n log n) over O(n²). Use hash maps for O(1) lookups.

## Database Queries
Use pagination; never `SELECT *` in production.
Batch inserts instead of looping individual INSERTs.
Add composite indexes for multi-column WHERE / ORDER BY.

## Caching
Cache expensive computations with TTL-based invalidation.
Use Redis for shared cache in distributed systems.

## Python Specifics
Use generators for large sequences to avoid memory spikes.
Profile with cProfile / py-spy before optimising.
""",
        }
        for filename, content in seeds.items():
            (docs_path / filename).write_text(content, encoding="utf-8")
        log.info("seeded_default_knowledge_docs", count=len(seeds))


_kb: Optional[EngineeringKnowledgeBase] = None


def get_knowledge_base() -> EngineeringKnowledgeBase:
    global _kb
    if _kb is None:
        _kb = EngineeringKnowledgeBase().build_or_load()
    return _kb
