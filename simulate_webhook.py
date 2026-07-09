"""
simulate_webhook.py — Fires a fake GitHub `pull_request` webhook event at your
local backend, signed the same way GitHub signs real deliveries, so you can
verify /webhook/github works BEFORE pushing/deploying.

Usage:
    python simulate_webhook.py
"""
import hmac
import hashlib
import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

SECRET = os.environ["GITHUB_WEBHOOK_SECRET"]  # must match your local .env
TARGET_URL = "http://localhost:8000/webhook/github"  # change port if different

# Minimal fake payload — just the fields webhook.py actually reads.
payload = {
    "action": "opened",
    "repository": {
        "name": "PrismAI",
        "owner": {"login": "AGNIHOTRIMAHI"},
    },
    "pull_request": {
        "number": 1,
        "html_url": "https://github.com/AGNIHOTRIMAHI/PrismAI/pull/1",
        "head": {"sha": "fake-sha-for-local-testing-0001"},
    },
}

body = json.dumps(payload).encode()
signature = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()

resp = requests.post(
    TARGET_URL,
    data=body,
    headers={
        "Content-Type": "application/json",
        "X-GitHub-Event": "pull_request",
        "X-Hub-Signature-256": signature,
    },
)

print(f"Status: {resp.status_code}")
print(f"Body: {resp.text}")