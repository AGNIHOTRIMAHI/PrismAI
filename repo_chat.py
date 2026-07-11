"""
repo_chat.py — LangGraph-based CRAG chat for PrismAI
Replaces the original inline-function version.
External interface is identical: answer_repo_question(...) — no changes needed in main.py or chat_with_repo.py
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from typing import Annotated, Any, Optional, TypedDict

import requests
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
import chat_store

log = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()


GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY_CHAT") or os.getenv("GOOGLE_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "")
RELEVANCE_THRESHOLD = 0.45

# ── In-memory FAISS cache so we don't re-index the same repo twice ──────────
_faiss_cache: dict[str, FAISS] = {}

# ── LangGraph state ──────────────────────────────────────────────────────────

class RepoChatState(TypedDict):
    repo_url: str
    question: str
    history: list[list[str]]
    token: Optional[str]
    retrieved_docs: list[Document]
    relevance_score: float
    web_results: list[Document]
    answer: str
    sources: list[str]
    crag_triggered_web_search: bool


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_repo(repo_url: str) -> tuple[str, str]:
    """Extract owner and repo name from a GitHub URL or 'owner/repo' string."""
    repo_url = repo_url.strip().rstrip("/")
    match = re.search(r"github\.com/([^/]+)/([^/]+?)(?:/|\.git|$)", repo_url)
    if match:
        return match.group(1), match.group(2)
    parts = repo_url.split("/")
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    raise ValueError(f"Cannot parse repo URL: {repo_url}")


def _fetch_repo_files(owner: str, repo: str, token: Optional[str]) -> list[Document]:
    """Fetch all text files from a GitHub repo via the API (recursive tree walk)."""
    headers = {"Authorization": f"token {token}"} if token else {}
    base = f"https://api.github.com/repos/{owner}/{repo}"

    # Get default branch
    r = requests.get(base, headers=headers, timeout=15)
    r.raise_for_status()
    branch = r.json().get("default_branch", "main")

    # Fetch full git tree
    r = requests.get(f"{base}/git/trees/{branch}?recursive=1", headers=headers, timeout=30)
    r.raise_for_status()
    tree = r.json().get("tree", [])

    text_exts = {".py", ".md", ".txt", ".js", ".ts", ".jsx", ".tsx",
                 ".yaml", ".yml", ".json", ".toml", ".cfg", ".ini", ".sh"}
    skip_dirs = {"node_modules", ".git", "dist", "build", "__pycache__", ".venv", "venv"}

    docs: list[Document] = []
    for item in tree:
        if item.get("type") != "blob":
            continue
        path: str = item["path"]
        if any(bad in path.split("/") for bad in skip_dirs):
            continue
        ext = os.path.splitext(path)[1].lower()
        if ext not in text_exts:
            continue
        if item.get("size", 0) > 200_000:  # skip huge files
            continue
        try:
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
            resp = requests.get(raw_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                docs.append(Document(page_content=resp.text, metadata={"source": path, "repo": f"{owner}/{repo}"}))
        except Exception as e:
            log.warning("Skipping %s: %s", path, e)

    log.info("Fetched %d files from %s/%s", len(docs), owner, repo)
    return docs

import hashlib

_FAISS_DISK_DIR = os.path.join(tempfile.gettempdir(), "prismai_faiss_cache")

def _get_or_build_index(repo_url: str, token: Optional[str]) -> FAISS:
    """Return a cached FAISS index for the repo, building it if needed."""
    cache_key = repo_url.strip().rstrip("/")
    if cache_key in _faiss_cache:
        log.info("FAISS cache hit (memory) for %s", cache_key)
        return _faiss_cache[cache_key]

    owner, repo = _parse_repo(repo_url)
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=GEMINI_API_KEY or None,
    )

    DEV_SAMPLE_RATIO = float(os.getenv("DEV_SAMPLE_RATIO", "1.0"))
    cache_suffix = f"_sample{DEV_SAMPLE_RATIO}" if DEV_SAMPLE_RATIO < 1.0 else ""
    disk_path = os.path.join(_FAISS_DISK_DIR, hashlib.md5(cache_key.encode()).hexdigest() + cache_suffix)

    if os.path.isdir(disk_path):
        log.info("FAISS cache hit (disk) for %s", cache_key)
        index = FAISS.load_local(disk_path, embeddings, allow_dangerous_deserialization=True)
        _faiss_cache[cache_key] = index
        return index

    docs = _fetch_repo_files(owner, repo, token)
    if not docs:
        raise ValueError(f"No indexable files found in {owner}/{repo}")
    
        # ── DEV MODE: only index a fraction of the repo to stay under free-tier quota ──
    DEV_SAMPLE_RATIO = float(os.getenv("DEV_SAMPLE_RATIO", "1.0"))  # e.g. 0.1 = 10%
    if DEV_SAMPLE_RATIO < 1.0:
        sample_size = max(1, int(len(docs) * DEV_SAMPLE_RATIO))
        docs = docs[:sample_size]
        log.warning("DEV MODE: sampling %d files (%.0f%%) for %s/%s",
                    sample_size, DEV_SAMPLE_RATIO * 100, owner, repo)


    splitter = RecursiveCharacterTextSplitter(chunk_size=3000, chunk_overlap=300)
    chunks = splitter.split_documents(docs)
    log.info("Indexing %d chunks for %s/%s", len(chunks), owner, repo)

    index = FAISS.from_documents(chunks, embeddings)
    os.makedirs(_FAISS_DISK_DIR, exist_ok=True)
    index.save_local(disk_path)
    _faiss_cache[cache_key] = index
    return index

def _grade_relevance(question: str, docs: list[Document]) -> float:
    """Ask Gemini to score how relevant the retrieved docs are to the question (0–1)."""
    if not docs:
        return 0.0
    llm = ChatGoogleGenerativeAI(model=GOOGLE_MODEL, google_api_key=GEMINI_API_KEY, temperature=0)
    context = "\n\n".join(d.page_content[:600] for d in docs[:4])
    prompt = f"""Rate how relevant the following code/docs are to the question on a scale of 0.0 to 1.0.
Return ONLY a decimal number, nothing else.

Question: {question}

Retrieved context:
{context}

Relevance score (0.0 = not relevant, 1.0 = highly relevant):"""
    try:
        resp = llm.invoke(prompt)
        return min(1.0, max(0.0, float(resp.content.strip())))
    except Exception:
        return 0.5


def _tavily_search(query: str) -> list[Document]:
    """Fetch web results via Tavily for CRAG correction step."""
    if not TAVILY_API_KEY:
        log.warning("TAVILY_API_KEY not set — skipping web search correction step")
        return []
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_API_KEY)
        results = client.search(query=query, max_results=3)
        return [
            Document(
                page_content=r.get("content", ""),
                metadata={"source": r.get("url", "web"), "title": r.get("title", "")}
            )
            for r in results.get("results", [])
        ]
    except Exception as e:
        log.warning("Tavily search failed: %s", e)
        return []


# ── LangGraph nodes ──────────────────────────────────────────────────────────

def retrieve_node(state: RepoChatState) -> dict:
    log.info("[CRAG] retrieve_node | q=%r", state["question"][:60])
    index = _get_or_build_index(state["repo_url"], state["token"])
    docs = index.similarity_search(state["question"], k=6)
    return {"retrieved_docs": docs}


def grade_node(state: RepoChatState) -> dict:
    score = _grade_relevance(state["question"], state["retrieved_docs"])
    log.info("[CRAG] grade_node | relevance=%.2f (threshold=%.2f)", score, RELEVANCE_THRESHOLD)
    return {"relevance_score": score}


def web_search_node(state: RepoChatState) -> dict:
    owner, repo = _parse_repo(state["repo_url"])
    query = f"{state['question']} {owner}/{repo} GitHub"
    log.info("[CRAG] web_search_node | query=%r", query)
    web_docs = _tavily_search(query)
    return {"web_results": web_docs, "crag_triggered_web_search": True}


def generate_node(state: RepoChatState) -> dict:
    llm = ChatGoogleGenerativeAI(
        model=GOOGLE_MODEL,
        google_api_key=GEMINI_API_KEY,
        temperature=0.3,
    )
    owner, repo = _parse_repo(state["repo_url"])

    # Build context from repo docs + optional web results
    repo_context = "\n\n".join(
        f"[{d.metadata.get('source', 'unknown')}]\n{d.page_content[:800]}"
        for d in state["retrieved_docs"][:5]
    )
    web_context = ""
    if state.get("web_results"):
        web_context = "\n\nAdditional web context:\n" + "\n\n".join(
            f"[{d.metadata.get('source', 'web')}]\n{d.page_content[:500]}"
            for d in state["web_results"][:3]
        )

    # Build conversation history string
    history_str = ""
    for turn in (state.get("history") or [])[-4:]:
        if len(turn) == 2:
            history_str += f"User: {turn[0]}\nAssistant: {turn[1]}\n\n"

    prompt = f"""You are an expert assistant helping a developer understand the GitHub repository {owner}/{repo}.
Answer the question using the provided code/documentation context.
Be specific, reference file paths when relevant, and keep the answer concise.

{history_str}Repository context:
{repo_context}{web_context}

Question: {state["question"]}

Answer:"""

    resp = llm.invoke(prompt)
    sources = list({d.metadata.get("source", "") for d in state["retrieved_docs"][:5]})

    return {
        "answer": resp.content.strip(),
        "sources": sources,
        "crag_triggered_web_search": state.get("crag_triggered_web_search", False),
    }


def route_decision(state: RepoChatState) -> str:
    """Conditional edge: route to web_search if relevance is low, else go straight to generate."""
    if state["relevance_score"] < RELEVANCE_THRESHOLD:
        log.info("[CRAG] routing → web_search_node (score=%.2f)", state["relevance_score"])
        return "web_search"
    log.info("[CRAG] routing → generate_node (score=%.2f)", state["relevance_score"])
    return "generate"


# ── Build and compile the graph ───────────────────────────────────────────────

def _build_graph() -> Any:
    builder = StateGraph(RepoChatState)

    builder.add_node("retrieve", retrieve_node)
    builder.add_node("grade", grade_node)
    builder.add_node("web_search", web_search_node)
    builder.add_node("generate", generate_node)

    builder.add_edge(START, "retrieve")
    builder.add_edge("retrieve", "grade")
    builder.add_conditional_edges(
        "grade",
        route_decision,
        {"web_search": "web_search", "generate": "generate"},
    )
    builder.add_edge("web_search", "generate")
    builder.add_edge("generate", END)

    _checkpoint_path = os.path.join(os.path.dirname(__file__), "data", "langgraph_checkpoints.db")
    os.makedirs(os.path.dirname(_checkpoint_path), exist_ok=True)
    _conn = sqlite3.connect(_checkpoint_path, check_same_thread=False)
    checkpointer = SqliteSaver(_conn)
    return builder.compile(checkpointer=checkpointer)



_graph = _build_graph()


# ── Public interface (unchanged from original) ────────────────────────────────


def answer_repo_question(
    repo_url: str,
    question: str,
    history: list[list[str]] | None = None,
    token: Optional[str] = None,
    thread_id: Optional[str] = None,
    github_user: Optional[str] = None,   # NEW
) -> dict:
    if not thread_id:
        owner, repo = _parse_repo(repo_url)
        thread_id = f"repochat_{owner}_{repo}"

    initial_state: RepoChatState = {
        "repo_url": repo_url,
        "question": question,
        "history": history or [],
        "token": token,
        "retrieved_docs": [],
        "relevance_score": 0.0,
        "web_results": [],
        "answer": "",
        "sources": [],
        "crag_triggered_web_search": False,
    }

    config = {"configurable": {"thread_id": thread_id}}

    try:
        final = _graph.invoke(initial_state, config=config)
        result = {
            "answer": final["answer"],
            "sources": final["sources"],
            "crag_relevance_score": round(final["relevance_score"], 3),
            "crag_triggered_web_search": final["crag_triggered_web_search"],
        }
        # NEW — persist for resume feature
        chat_store.create_session_if_missing(thread_id, repo_url, github_user, question)
        chat_store.save_turn(thread_id, question, result)
        return result
    except Exception as e:
        log.error("CRAG graph error: %s", e, exc_info=True)
        return {
            "answer": f"Sorry, I encountered an error: {e}",
            "sources": [],
            "crag_relevance_score": 0.0,
            "crag_triggered_web_search": False,
        }