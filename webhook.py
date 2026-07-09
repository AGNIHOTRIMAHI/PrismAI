"""
webhook.py — GitHub webhook receiver for connected repos.
"""
import hmac, hashlib, json
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from config import get_settings
from graph import pr_review_graph as graph
import db

router = APIRouter()

def _verify_signature(payload_body: bytes, signature_header: str) -> bool:
    settings = get_settings()
    if not signature_header:
        return False
    expected = "sha256=" + hmac.new(
        settings.github_webhook_secret.encode(), payload_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)

@router.post("/webhook/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_signature(body, signature):
        raise HTTPException(401, "Invalid signature")

    if request.headers.get("X-GitHub-Event") != "pull_request":
        return {"status": "ignored"}

    payload = json.loads(body)
    if payload.get("action") not in ("opened", "synchronize", "reopened"):
        return {"status": "ignored", "reason": payload.get("action")}

    owner = payload["repository"]["owner"]["login"]
    repo = payload["repository"]["name"]
    pr_number = payload["pull_request"]["number"]
    sha = payload["pull_request"]["head"]["sha"]
    pr_url = payload["pull_request"]["html_url"]

    if db.already_processed(owner, repo, pr_number, sha):
        return {"status": "skipped", "reason": "already processed"}
    db.mark_processed(owner, repo, pr_number, sha)

    import uuid
    thread_id = str(uuid.uuid4())
    db.create_run(thread_id, pr_url, owner, repo, pr_number, trigger_source="webhook")

    config = {
        "configurable": {"thread_id": thread_id},
        "run_name": f"pr_review::{pr_number}",
        "tags": ["pr-review", "webhook"],
        "metadata": {"pr_url": pr_url, "thread_id": thread_id},
    }
    initial_state = {"pr_url": pr_url, "github_token": None}
    background_tasks.add_task(graph.invoke, initial_state, config)

    return {"status": "accepted", "thread_id": thread_id}