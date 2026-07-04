from dotenv import load_dotenv
load_dotenv()  # ← must come before anything that reads env vars
import os

# ── TEMPORARY: verify LangSmith env vars loaded correctly ──────────────────
print("LangSmith tracing enabled:", os.getenv("LANGSMITH_TRACING"))
print("LangSmith project:", os.getenv("LANGSMITH_PROJECT"))
# ─────────────────────────────────────────────────────────────────────────


# ── Hide sensitive input data from LangSmith traces ─────────────────────────
os.environ["LANGSMITH_HIDE_INPUTS"] = "true"
os.environ["LANGSMITH_HIDE_OUTPUTS"] = "false"
# ─────────────────────────────────────────────────────────────────────────

import logging
import requests
import secrets
from typing import Optional
from dotenv import load_dotenv
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from state import PRReviewState
from datetime import datetime, timezone
from graph import pr_review_graph as graph
from repo_chat import answer_repo_question
# load_dotenv(override=True)


class ChatRequest(BaseModel):
    repo_url: str
    question: str
    history: list[list[str]] = []
    github_token: Optional[str] = None
    thread_id: Optional[str] = None





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


def post_github_comment(pr_url: str, body: str,token: Optional[str] = None) -> tuple[bool, str]:
    active_token = token or GITHUB_TOKEN
    if not active_token:
        return False, "No GitHub token available to post comment."
    try:
        clean_url = pr_url.strip().rstrip("/")
        parts     = clean_url.split("github.com/")[1].split("/")
        owner     = parts[0]
        repo      = parts[1]
        pr_number = parts[3]
        api_url   = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
        headers   = {
            "Authorization": f"token {active_token}",
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
    #response = RedirectResponse(FRONTEND_URL)
    response = RedirectResponse(f"{FRONTEND_URL}?session_id={session_id}")
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

class RepoChatRequest(BaseModel):
    repo_url: str
    question: str
    history: list[list[str]] = []
    github_token: Optional[str] = None
    thread_id: Optional[str] = None 
 
# -----------------------------------------------------------------------------
# HELPER: pull the logged-in user's GitHub token server-side, e.g. inside
# /review, so PRs are fetched using THEIR permissions instead of a shared PAT
# -----------------------------------------------------------------------------
def get_session_token(request: Request) -> Optional[str]:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    session = SESSIONS.get(session_id) if session_id else None
    return session.get("access_token") if session else None

# -----------------------------------------------------------------------------
class ReviewRequest(BaseModel):
    pr_url:    str
    thread_id: str
    github_token: Optional[str] = None

class ApprovalRequest(BaseModel):
    thread_id: str
    approved:  bool
    pr_url:    str
    user_token: Optional[str] = None


# -----------------------------------------------------------------------------
# 3. ENDPOINTS
# -----------------------------------------------------------------------------
@app.post("/review")
async def start_review(req: ReviewRequest, background_tasks: BackgroundTasks):
    log.info("=== NEW REVIEW REQUEST  thread=%s  url=%s ===", req.thread_id, req.pr_url)

    
    #config = {"configurable": {"thread_id": req.thread_id}}
    config = {
    "configurable": {"thread_id": req.thread_id},
    "run_name": f"pr_review::{req.pr_url.split('/')[-1]}",
    "tags": ["pr-review", "background"],
    "metadata": {"pr_url": req.pr_url, "thread_id": req.thread_id},
   }
    initial_state = {
        
        "pr_url":     req.pr_url,
        "github_token": req.github_token,
    }

    log.info("Offloading LangGraph pipeline to background worker...")
    # FIX 2: Run the graph in the background so the server doesn't freeze!
    background_tasks.add_task(graph.invoke, initial_state, config)
    
    return {"status": "pipeline_started"}


@app.get("/state/{thread_id}")
async def get_state(thread_id: str):
    config     = {"configurable": {"thread_id": thread_id}}
    state_info = graph.get_state(config)
    if not state_info or not state_info.values:
        return {"values": {}, "waiting_for_human": False, "done": False}
 
    values = state_info.values
    next_nodes = set(state_info.next) if state_info.next else set()
 
    is_at_hitl_interrupt = "human_review_interrupt" in next_nodes
    agents_fully_done = (
        "security_report"       in values and
        "crag_enhanced_context" in values
    )
 
    waiting_for_human = is_at_hitl_interrupt and agents_fully_done
    #Graph is done when: no next nodes, has final output, not waiting for human
    done = (
        not state_info.next
        and not waiting_for_human
        and bool(values.get("final_report_markdown"))
    )
 
    return {
        "values":            values,
        "waiting_for_human": waiting_for_human,
        "done":              done,
    }

@app.post("/approve")
async def approve_pipeline(req: ApprovalRequest, request: Request):
    log.info("=== APPROVAL  thread=%s  approved=%s ===", req.thread_id, req.approved)
    #config = {"configurable": {"thread_id": req.thread_id}}

    # WITH THIS
    config = {
    "configurable": {"thread_id": req.thread_id},
    "run_name": f"pr_review_resume::{req.thread_id[:8]}",
    "tags": ["pr-review", "hitl-resume"],
    "metadata": {"pr_url": req.pr_url, "thread_id": req.thread_id, "approved": req.approved},
    }
    session_token = get_session_token(request) 
    active_token  = session_token or req.user_token or os.getenv("GITHUB_TOKEN")
    graph.update_state(config, {
    "hitl_decision": {
        "reviewer":  "senior_engineer",
        "decision":  "approve" if req.approved else "request_changes",
        "comment":   "Approved via PrismAI HITL gate." if req.approved else "Changes requested via PrismAI HITL gate.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
   }, as_node="human_review_interrupt")
    graph.invoke(None, config)
    state_info = graph.get_state(config)
    final_report = state_info.values.get("final_report_markdown", "")
    if final_report and req.pr_url:
        success, msg = post_github_comment(
            pr_url=req.pr_url,
            body=final_report,
            token=active_token,  # Using the prioritized token
        )
        log.info("GitHub comment posted: %s — %s", success, msg)
    return {"status": "done", "approved": req.approved}

@app.post("/chat/repo")
async def chat_repo(req: ChatRequest):
    result = answer_repo_question(
        repo_url=req.repo_url,
        question=req.question,
        history=req.history,
        token=req.github_token,
        thread_id=req.thread_id,
    )
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
