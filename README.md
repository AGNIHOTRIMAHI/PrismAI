# PrismAI 🪐 — Autonomous PR Review Agent

> An AI-powered Pull Request reviewer built with **LangGraph**, **FastAPI**, and a real-time terminal UI. PrismAI autonomously fetches, analyzes, and reports on GitHub PRs using a multi-agent graph with CRAG retrieval, security scoring, and a Human-In-The-Loop (HITL) interrupt system.

---

## ✨ Features

- **Multi-Agent LangGraph Pipeline** — Modular graph nodes for fetching, CRAG retrieval, security analysis, performance review, style checking, and aggregation
- **CRAG (Corrective RAG)** — Relevance-scored document retrieval with automatic web search fallback when index confidence is low
- **Security Guardrails** — Quantified risk scoring (0–10); automatically halts execution and triggers HITL when score ≥ 7
- **Human-In-The-Loop (HITL)** — Interrupt mechanism that freezes graph state and requires an operator decision (Approve / Reject / Escalate) before resuming
- **GitHub Integration** — Automatically posts the review report as a comment on the PR
- **Real-Time Terminal UI** — Live execution trace, pipeline step indicators, CRAG diagnostics panel, and review output with markdown rendering
- **Backend Health Monitor** — Live green/red indicator showing backend connectivity status

---

## 🖥️ UI Overview

```
┌─────────────────────────────────────────────────────────────┐
│  PrismAI 🪐          [PR URL Input]          [Execute Graph] │
├──────────────────────────────────────────────────────────────┤
│  fetcher › crag › security › performance › style › aggregator › hitl  │
├─────────────────────────┬────────────────────────────────────┤
│  CRAG Diagnostics Card  │                                    │
├─────────────────────────┤    Review Output (Markdown)        │
│                         │                                    │
├─────────────────────────┴────────────────────────────────────┤
│  Live Intelligence Feed      │  Human-In-The-Loop Panel      │
│  (Execution Trace Terminal)  │  (HITL Decision Interface)    │
└──────────────────────────────┴───────────────────────────────┘
```

---

## 🏗️ Architecture

```
GitHub PR URL
      │
      ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   fetcher   │────▶│     crag     │────▶│    security     │
│  (GitHub    │     │  (Retrieval  │     │  (Risk Scoring  │
│   API)      │     │  + Web Search│     │   0–10)         │
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                  │
                                         score ≥ 7 → HITL INTERRUPT
                                                  │
                                                  ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│ performance │────▶│    style     │────▶│   aggregator    │
│   (Analysis)│     │  (Arch Review│     │  (Report Build) │
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                  │
                                                  ▼
                                         ┌─────────────────┐
                                         │  GitHub Comment │
                                         │  + UI Report    │
                                         └─────────────────┘
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Node.js (optional, for local serving)
- A GitHub Personal Access Token
- A Tavily API key (for CRAG web search fallback)
- A Google AI or Anthropic API key (for LLM)

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/prism-ai.git
cd prism-ai
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```env
# GitHub
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx

# Tavily (CRAG web search fallback)
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxxxx

# Gemini Model Settings
GOOGLE_MODEL=gemini-1.5-flash
GOOGLE_TEMPERATURE=0.1
GOOGLE_EMBEDDING_MODEL=models/gemini-embedding-001

# OR use Anthropic instead
# ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxx
```

> ⚠️ **Important:** `gemini-2.5-flash` has a free tier limit of 20 requests/day. Use `gemini-1.5-flash` for development or enable billing on your Google AI account.

### 4. Start the Backend

```bash
python main.py
# or
uvicorn main:app --reload --port 8000
```

### 5. Open the Frontend

Open `frontend/index.html` directly in your browser, or serve it locally:

```bash
npx serve frontend/
```

Navigate to `http://localhost:3000` (or wherever it's served).

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Backend health check |
| `POST` | `/review/trigger` | Start a new PR review |
| `GET` | `/review/{thread_id}` | Poll review status and results |
| `POST` | `/hitl/respond` | Submit a HITL operator decision |

### `POST /review/trigger`

```json
{
  "pr_url": "https://github.com/owner/repo/pull/42"
}
```

**Response:**
```json
{
  "thread_id": "manual-ab90b4ec385d"
}
```

### `GET /review/{thread_id}`

**Response:**
```json
{
  "thread_id": "manual-ab90b4ec385d",
  "pr_url": "https://github.com/owner/repo/pull/42",
  "status": "completed",
  "security_score": 3,
  "is_ready_for_merge": true,
  "hitl_required": false,
  "github_comment_id": 1234567890,
  "github_comment_url": "https://github.com/owner/repo/pull/42#issuecomment-...",
  "final_report_markdown": "# PR Review Report\n\n...",
  "crag_relevance_score": 0.87,
  "crag_triggered_web_search": false,
  "retrieved_docs": ["doc1", "doc2"],
  "error": null
}
```

### `POST /hitl/respond`

```json
{
  "thread_id": "manual-ab90b4ec385d",
  "decision": "approve",
  "reviewer_id": "admin.yash",
  "comment": "Reviewed manually. Security findings are acceptable."
}
```

`decision` can be: `approve` | `request_changes` | `escalate`

---

## 🔁 HITL Flow

```
Security Score ≥ 7
        │
        ▼
Graph execution FROZEN
        │
        ▼
Operator sees HITL panel in UI
        │
   ┌────┴────────────────────┐
   │                         │
Approve                 Request Changes / Escalate
   │                         │
Graph resumes           PR flagged / quarantined
   │
GitHub comment posted
```

---

## 🧠 LangGraph Node Output Schema

Each node should return state fields that the frontend and downstream nodes consume:

```python
# Minimum expected state output from your graph nodes
return {
    "status": "completed",                        # running | completed | awaiting_human
    "security_score": 3,                          # int 0–10
    "is_ready_for_merge": False,                  # bool
    "hitl_required": False,                       # bool
    "final_report_markdown": "# Report\n...",     # full markdown string
    "github_comment_id": 1234567890,              # int or None
    "github_comment_url": "https://...",          # str or None
    "crag_relevance_score": 0.87,                 # float 0–1
    "crag_triggered_web_search": False,           # bool
    "retrieved_docs": ["doc1", "doc2"],           # list[str]
    "execution_log": ["fetcher", "crag", "security", "aggregator"],  # list[str]
    "error": None                                 # str or None
}
```

---

## 📁 Project Structure

```
prism-ai/
├── main.py                  # FastAPI app entry point
├── graph/
│   ├── builder.py           # LangGraph graph definition
│   ├── nodes/
│   │   ├── fetcher.py       # GitHub PR fetcher node
│   │   ├── crag.py          # CRAG retrieval node
│   │   ├── security.py      # Security analysis node
│   │   ├── performance.py   # Performance review node
│   │   ├── style.py         # Style/architecture node
│   │   ├── aggregator.py    # Report aggregator node
│   │   └── hitl.py          # Human-in-the-loop node
│   └── state.py             # Shared graph state schema
├── frontend/
│   └── index.html           # PrismAI terminal UI
├── .env                     # Environment variables (not committed)
├── .env.example             # Template for environment variables
├── requirements.txt
└── README.md
```

---
## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent Orchestration | [LangGraph](https://github.com/langchain-ai/langgraph) |
| Backend API | [FastAPI](https://fastapi.tiangolo.com/) |
| LLM | Google Gemini / Anthropic Claude |
| Retrieval | CRAG + [Tavily](https://tavily.com/) web search |
| GitHub Integration | PyGithub / GitHub REST API |
| Frontend | Vanilla HTML/CSS/JS (no framework) |
| Fonts | JetBrains Mono, Inter, Plus Jakarta Sans |

---

<div align="center">
    <strong>Built with LangGraph · FastAPI · ❤️</strong><br/>
  <sub>PrismAI — because every PR deserves a second pair of eyes</sub>
</div>


  <strong>Built with LangGraph · FastAPI · ❤️</strong><br/>
  <sub>PrismAI — because every PR deserves a second pair of eyes</sub>
</div>
