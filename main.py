import os
import logging
import requests
import re
from typing import Optional
from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# -----------------------------------------------------------------------------
# LOGGING
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("prism")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

app = FastAPI(title="PrismAI Review Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows Streamlit to talk to FastAPI
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# 0. GITHUB DIFF FETCHING & POSTING
# -----------------------------------------------------------------------------
def fetch_github_diff(pr_url: str) -> tuple[Optional[str], Optional[str]]:
    clean_url = pr_url.strip().rstrip("/")
    if not clean_url.startswith("https://github.com/"):
        return None, "Invalid URL. Provide a valid GitHub Pull Request link."
    if not GITHUB_TOKEN:
        return None, "GITHUB_TOKEN not found in .env file."
    try:
        parts     = clean_url.split("github.com/")[1].split("/")
        owner     = parts[0]
        repo      = parts[1]
        pr_number = parts[3]
        api_url   = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        headers   = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3.diff",
        }
        log.info("Fetching diff: %s", api_url)
        resp = requests.get(api_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            log.info("Diff fetched successfully (%d chars)", len(resp.text))
            return resp.text, None
        else:
            return None, f"GitHub API returned {resp.status_code}."
    except Exception as e:
        return None, f"Connection error: {str(e)}"


def post_github_comment(pr_url: str, body: str) -> tuple[bool, str]:
    if not GITHUB_TOKEN:
        return False, "GITHUB_TOKEN missing"
    try:
        clean_url = pr_url.strip().rstrip("/")
        parts     = clean_url.split("github.com/")[1].split("/")
        owner     = parts[0]
        repo      = parts[1]
        pr_number = parts[3]
        api_url   = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
        headers   = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }
        log.info("Posting GitHub comment to: %s", api_url)
        resp = requests.post(api_url, headers=headers, json={"body": body}, timeout=10)
        if resp.status_code == 201:
            return True, "Comment posted."
        else:
            return False, f"GitHub returned {resp.status_code}: {resp.text}"
    except Exception as e:
        return False, str(e)


# -----------------------------------------------------------------------------
# 1. LANGGRAPH SETUP & REAL AI AGENTS
# -----------------------------------------------------------------------------
class AgentState(TypedDict):
    pr_id:             str
    pr_url:            str  
    repository:        str
    code_diff:         str
    security_feedback: Optional[str]
    security_score:    Optional[int] # <-- Frontend uses this to trigger HITL
    style_feedback:    Optional[str]
    crag_context:      Optional[str]
    human_approved:    Optional[bool]
    final_status:      Optional[str]

# Initialize Gemini Model
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1)

# ── Security Agent ──────────────────────────────────────────────────────────
def security_agent_node(state: AgentState):
    log.info("▶  REAL SECURITY AGENT running...")
    diff = state.get("code_diff", "")
    
    prompt = f"""You are an elite cybersecurity engineer reviewing a GitHub Pull Request.
    Review the following code diff for security vulnerabilities (e.g., injections, hardcoded secrets, dangerous functions).
    Provide a concise, professional markdown report of your findings.
    
    IMPORTANT: At the very end of your report, you MUST provide a risk score on a new line using this exact format:
    SCORE: X
    (Where X is an integer from 0 to 10. 0 = perfectly safe, 10 = critical vulnerability).
    
    CODE DIFF:
    {diff[:10000]} # Truncated for safety
    """
    
    response = llm.invoke(prompt).content
    
    # Extract the score using regex
    score = 0
    match = re.search(r'SCORE:\s*(\d+)', response)
    if match:
        score = int(match.group(1))
    
    # Clean up the report string by removing the raw score text
    clean_report = re.sub(r'SCORE:\s*\d+', '', response).strip()
    
    log.info(f"Security evaluation complete. Extracted Score: {score}/10")
    
    return {
        "security_feedback": clean_report,
        "security_score": score
    }

# ── Style & Performance Agent ───────────────────────────────────────────────
def style_agent_node(state: AgentState):
    log.info("▶  REAL STYLE & PERFORMANCE AGENT running...")
    diff = state.get("code_diff", "")
    
    prompt = f"""You are a strict principal software engineer. 
    Review this code diff ONLY for code styling, performance bottlenecks, and best practices.
    Ignore security issues (another agent handles that).
    Provide your feedback in short, concise bullet points.
    
    CODE DIFF:
    {diff[:10000]}
    """
    
    response = llm.invoke(prompt).content
    return {"style_feedback": response}

# ── CRAG / Diagnostics Node ──────────────────────────────────────────────────
def crag_tavily_node(state: AgentState):
    log.info("▶  CRAG EVALUATOR running...")
    diff = state.get("code_diff", "")
    
    prompt = f"""You are a Corrective RAG (CRAG) grounding evaluator.
    Analyze the syntax and libraries used in this code diff. 
    Provide a brief 3-sentence diagnostic confirming if the patterns match stable production release conventions or if deprecated features are used.
    
    CODE DIFF:
    {diff[:10000]}
    """
    
    response = llm.invoke(prompt).content
    return {"crag_context": f"🌐 CRAG Diagnostics:\n\n{response}"}

# ── Post Review Node ────────────────────────────────────────────────────────
# ── Post Review Node ────────────────────────────────────────────────────────
def post_review_node(state: AgentState):
    log.info("▶  POST REVIEW NODE running (human_approved=%s)...", state.get("human_approved"))

    is_approved = state.get("human_approved")
    score = state.get('security_score', 0)
    
    # 1. Determine the Header and Footer based on your decision
    if is_approved:
        status_header = "✅ **MERGE APPROVED**"
        footer_msg = "_Review authorised by a senior engineer via PrismAI HITL gate._"
    else:
        status_header = "🛑 **CHANGES REQUESTED (BLOCKED)**"
        footer_msg = "_Review blocked by a senior engineer via PrismAI HITL gate. Please address the critical security issues above._"

    # 2. Build the unified Markdown comment
    comment_body = (
        f"## 🛡️ PrismAI Automated Code Review\n\n"
        f"### Status: {status_header}\n\n"
        f"### Security Agent (Risk Score: {score}/10)\n{state.get('security_feedback', 'N/A')}\n\n"
        f"### Style & Performance Agent\n{state.get('style_feedback', 'N/A')}\n\n"
        f"### CRAG Grounding Evaluator\n{state.get('crag_context', 'N/A')}\n\n"
        f"{footer_msg}"
    )

    # 3. Post to GitHub regardless of approval status
    pr_url = state.get("pr_url", "")
    success, msg = post_github_comment(pr_url, comment_body)

    # 4. Return the status to your Streamlit Dashboard
    if success:
        if is_approved:
            return {"final_status": "🚀 Review pipeline authorised. Approval posted to GitHub!"}
        else:
            return {"final_status": "🛑 Review blocked. Rejection comment posted to GitHub PR."}
    else:
        return {"final_status": f"⚠️ GitHub post failed: {msg}"}
# ── Graph assembly ───────────────────────────────────────────────────────────
memory = MemorySaver()
workflow = StateGraph(AgentState)

workflow.add_node("security_agent", security_agent_node)
workflow.add_node("style_agent",    style_agent_node)
workflow.add_node("crag_tavily",    crag_tavily_node)
workflow.add_node("post_review",    post_review_node)

workflow.add_edge(START,             "security_agent")
workflow.add_edge("security_agent",  "style_agent")
workflow.add_edge("style_agent",     "crag_tavily")
workflow.add_edge("crag_tavily",     "post_review")
workflow.add_edge("post_review",     END)

# Interrupt BEFORE post_review so the human gate fires at the right point
graph = workflow.compile(checkpointer=memory, interrupt_before=["post_review"])


# -----------------------------------------------------------------------------
# 2. REQUEST / RESPONSE MODELS
# -----------------------------------------------------------------------------
class ReviewRequest(BaseModel):
    pr_url:    str
    thread_id: str


class ApprovalRequest(BaseModel):
    thread_id: str
    approved:  bool


# -----------------------------------------------------------------------------
# 3. ENDPOINTS
# -----------------------------------------------------------------------------
@app.post("/review")
async def start_review(req: ReviewRequest):
    log.info("=== NEW REVIEW REQUEST  thread=%s  url=%s ===", req.thread_id, req.pr_url)

    diff, error = fetch_github_diff(req.pr_url)
    if error:
        return {"error": error}

    diff_preview = diff[:1000] + "\n\n...[Truncated for Dashboard View]..." if len(diff) > 1000 else diff
    config = {"configurable": {"thread_id": req.thread_id}}

    initial_state = {
        "code_diff":  diff,
        "pr_url":     req.pr_url,
        "pr_id":      "PR-LIVE",
        "repository": req.pr_url,
    }

    log.info("Invoking LangGraph pipeline with Gemini...")
    graph.invoke(initial_state, config)
    return {"status": "pipeline_started", "diff_preview": diff_preview}


@app.get("/state/{thread_id}")
async def get_state(thread_id: str):
    config     = {"configurable": {"thread_id": thread_id}}
    state_info = graph.get_state(config)

    return {
        "values":            state_info.values,
        "waiting_for_human": bool(state_info.next),
        "done":              not bool(state_info.next) and bool(state_info.values.get("final_status")),
    }


@app.post("/approve")
async def approve_pipeline(req: ApprovalRequest):
    log.info("=== APPROVAL  thread=%s  approved=%s ===", req.thread_id, req.approved)
    config = {"configurable": {"thread_id": req.thread_id}}

    graph.update_state(config, {"human_approved": req.approved}, as_node="crag_tavily")
    graph.invoke(None, config)

    return {"status": "done", "approved": req.approved}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)