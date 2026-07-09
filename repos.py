"""
repos.py — Programmatically create/delete GitHub webhooks so users can
"connect" a repo for automatic reviews (persistent) without touching
GitHub's settings UI by hand.
"""
import os
import requests
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from config import get_settings
import db

router = APIRouter()

class ConnectRepoRequest(BaseModel):
    owner: str
    repo: str
    github_token: str  # needs admin:repo_hook scope on that repo
    notify_email: str
    
@router.post("/repos/connect")
async def connect_repo(req: ConnectRepoRequest):
    settings = get_settings()
    webhook_url = os.environ["WEBHOOK_PUBLIC_URL"]  # e.g. https://your-app.onrender.com/webhook/github

    resp = requests.post(
        f"https://api.github.com/repos/{req.owner}/{req.repo}/hooks",
        headers={"Authorization": f"token {req.github_token}"},
        json={
            "name": "web", "active": True, "events": ["pull_request"],
            "config": {
                "url": webhook_url, "content_type": "json",
                "secret": settings.github_webhook_secret,
            },
        },
    )
    if resp.status_code != 201:
        raise HTTPException(resp.status_code, f"GitHub rejected webhook creation: {resp.text}")

    webhook_id = resp.json()["id"]
    db.add_connected_repo(req.owner, req.repo, webhook_id, notify_email=req.notify_email)
    return {"status": "connected", "webhook_id": webhook_id}

class DisconnectRepoRequest(BaseModel):
    owner: str
    repo: str
    github_token: str

@router.post("/repos/disconnect")
async def disconnect_repo(req: DisconnectRepoRequest):
    webhook_id = db.get_webhook_id(req.owner, req.repo)
    if webhook_id:
        requests.delete(
            f"https://api.github.com/repos/{req.owner}/{req.repo}/hooks/{webhook_id}",
            headers={"Authorization": f"token {req.github_token}"},
        )
    db.remove_connected_repo(req.owner, req.repo)
    return {"status": "disconnected"}

@router.get("/repos")
async def get_connected_repos():
    return {"repos": db.list_connected_repos()}