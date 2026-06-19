import os
import logging
import requests
import re
import secrets
from typing import Optional
from dotenv import load_dotenv
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI
from state import PRReviewState
from agents.fetcher import fetcher_node
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
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:8501")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# 0. GITHUB DIFF FETCHING & POSTING
# -----------------------------------------------------------------------------
def fetch_github_diff(pr_url: str,token: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    clean_url = pr_url.strip().rstrip("/")
    if not clean_url.startswith("https://github.com/"):
        return None, "Invalid URL. Provide a valid GitHub Pull Request link."
    active_token = token or GITHUB_TOKEN
    if not active_token:
        return None, "No GitHub token provided in UI and GITHUB_TOKEN not found in server env."
    try:
        parts     = clean_url.split("github.com/")[1].split("/")
        owner     = parts[0]
        repo      = parts[1]
        pr_number = parts[3]
        api_url   = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        headers   = {
            "Authorization": f"token {active_token}",
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

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI")        # e.g. https://your-backend/auth/github/callback
FRONTEND_URL = os.getenv("FRONTEND_URL")                    # e.g. https://your-streamlit-app.streamlit.app
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"  # False only for local http testing
 
# In-memory session store: { session_id: {"access_token": ..., "user": {...}} }
# Swap this for Redis in production — in-memory won't survive a server restart
# or work across multiple backend instances.
SESSIONS: dict[str, dict] = {}
 
SESSION_COOKIE_NAME = "prismai_session"
 
 
# -----------------------------------------------------------------------------
# 1. KICK OFF LOGIN — Streamlit links/redirects the browser here
# -----------------------------------------------------------------------------
@app.get("/auth/github/login")
async def github_login():
    state = secrets.token_urlsafe(16)  # CSRF protection
    SESSIONS[f"state_{state}"] = {"pending": True}
 
    github_authorize_url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={OAUTH_REDIRECT_URI}"
        f"&scope=repo read:user"
        f"&state={state}"
    )
    return RedirectResponse(github_authorize_url)
 
 
# -----------------------------------------------------------------------------
# 2. GITHUB REDIRECTS BACK HERE WITH ?code=...&state=...
# -----------------------------------------------------------------------------
@app.get("/auth/github/callback")
async def github_callback(code: str, state: str):
    if SESSIONS.pop(f"state_{state}", None) is None:
        return JSONResponse({"error": "Invalid OAuth state"}, status_code=400)
 
    # Exchange code for access token
    token_resp = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": OAUTH_REDIRECT_URI,
        },
        timeout=10,
    )
    token_data = token_resp.json()
    access_token = token_data.get("access_token")
 
    if not access_token:
        log.error("GitHub OAuth token exchange failed: %s", token_data)
        return RedirectResponse(f"{FRONTEND_URL}?auth_error=1")
 
    # Fetch user profile
    user_resp = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"token {access_token}"},
        timeout=10,
    )
    user_data = user_resp.json() if user_resp.status_code == 200 else {}
 
    # Create a server-side session
    session_id = secrets.token_urlsafe(32)
    SESSIONS[session_id] = {
        "access_token": access_token,   # GitHub token stays server-side only
        "user": {
            "login": user_data.get("login"),
            "avatar_url": user_data.get("avatar_url"),
            "name": user_data.get("name"),
        },
    }
 
    log.info("OAuth login success for user: %s", user_data.get("login"))
 
    # Redirect back to the Streamlit frontend, set HttpOnly cookie
    response = RedirectResponse(FRONTEND_URL)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,           # JS cannot read this — XSS-proof
        secure=COOKIE_SECURE,     # True in production (HTTPS only)
        samesite="lax",           # allows the GitHub redirect to carry the cookie back
        max_age=60 * 60 * 24 * 7,  # 7 days
    )
    return response
 
 
# -----------------------------------------------------------------------------
# 3. STREAMLIT CALLS THIS ON EVERY LOAD TO CHECK LOGIN STATE
# -----------------------------------------------------------------------------
@app.get("/auth/me")
async def auth_me(request: Request):
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    session = SESSIONS.get(session_id) if session_id else None
 
    if not session or "user" not in session:
        return {"logged_in": False, "user": None}
 
    return {"logged_in": True, "user": session["user"]}
 
 
# -----------------------------------------------------------------------------
# 4. LOGOUT
# -----------------------------------------------------------------------------
@app.post("/auth/logout")
async def auth_logout(request: Request):
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        SESSIONS.pop(session_id, None)
 
    response = JSONResponse({"status": "logged_out"})
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response
 
 
# -----------------------------------------------------------------------------
# HELPER: pull the logged-in user's GitHub token server-side, e.g. inside
# /review, so PRs are fetched using THEIR permissions instead of a shared PAT
# -----------------------------------------------------------------------------
def get_session_token(request: Request) -> Optional[str]:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    session = SESSIONS.get(session_id) if session_id else None
    return session.get("access_token") if session else None
# -----------------------------------------------------------------------------
# 1. LANGGRAPH SETUP & REAL AI AGENTS
# -----------------------------------------------------------------------------
#class AgentState(TypedDict):
#    pr_id:             str
#    pr_url:            str  
 #   repository:        str
 #   code_diff:         str
 #   security_feedback: Optional[str]
 #   security_score:    Optional[int] # <-- Frontend uses this to trigger HITL
 #   style_feedback:    Optional[str]
 #   crag_context:      Optional[str]
 #   human_approved:    Optional[bool]
 #   final_status:      Optional[str]

# Initialize Gemini Model
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1)

# ── Security Agent ──────────────────────────────────────────────────────────
def security_agent_node(state: PRReviewState):
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
def style_agent_node(state:PRReviewState):
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
def crag_tavily_node(state:PRReviewState):
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
def post_review_node(state: PRReviewState):
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
workflow = StateGraph(PRReviewState)
workflow.add_node("fetcher",        fetcher_node)    
workflow.add_node("security_agent", security_agent_node)
workflow.add_node("style_agent",    style_agent_node)
workflow.add_node("crag_tavily",    crag_tavily_node)
workflow.add_node("post_review",    post_review_node)

workflow.add_edge(START,             "fetcher")
workflow.add_edge("fetcher",  "security_agent")
workflow.add_edge("security_agent", "style_agent")
workflow.add_edge("style_agent",    "crag_tavily")
workflow.add_edge("crag_tavily",    "post_review")
workflow.add_edge("post_review",    END)

# Interrupt BEFORE post_review so the human gate fires at the right point
graph = workflow.compile(checkpointer=memory, interrupt_before=["post_review"])


# -----------------------------------------------------------------------------
# 2. REQUEST / RESPONSE MODELS
# -----------------------------------------------------------------------------
class ReviewRequest(BaseModel):
    pr_url:    str
    thread_id: str
    github_token: Optional[str] = None

class ApprovalRequest(BaseModel):
    thread_id: str
    approved:  bool


# -----------------------------------------------------------------------------
# 3. ENDPOINTS
# -----------------------------------------------------------------------------
@app.post("/review")
async def start_review(req: ReviewRequest, background_tasks: BackgroundTasks):
    log.info("=== NEW REVIEW REQUEST  thread=%s  url=%s ===", req.thread_id, req.pr_url)

    diff, error = fetch_github_diff(req.pr_url, req.github_token)
    if error:
        log.error("Aborting review pipeline: %s", error)
        # FIX 1: Raise actual HTTP error so Streamlit knows it failed!
        raise HTTPException(status_code=400, detail=error)

    diff_preview = diff[:1000] + "\n\n...[Truncated for Dashboard View]..." if len(diff) > 1000 else diff
    config = {"configurable": {"thread_id": req.thread_id}}

    initial_state = {
        "code_diff":  diff,
        "pr_url":     req.pr_url,
        "pr_id":      "PR-LIVE",
        "repository": req.pr_url,
        "github_token": req.github_token,
    }

    log.info("Offloading LangGraph pipeline to background worker...")
    # FIX 2: Run the graph in the background so the server doesn't freeze!
    background_tasks.add_task(graph.invoke, initial_state, config)
    
    return {"status": "pipeline_started", "diff_preview": diff_preview}


@app.get("/state/{thread_id}")
async def get_state(thread_id: str):
    config     = {"configurable": {"thread_id": thread_id}}
    state_info = graph.get_state(config)

    return {
        "values":state_info.values,
        "waiting_for_human": bool(state_info.next),   # True when graph is interrupted (next node exists)
        "done": not bool(state_info.next) and bool(state_info.values.get("final_report_markdown")),
       
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