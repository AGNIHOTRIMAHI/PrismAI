"""
db.py — Lightweight SQLite tracking for runs and connected repos.
Separate from the LangGraph checkpointer (prism_memory.sqlite), which only
stores per-thread graph state, not a queryable list across all runs.
"""
import sqlite3
from datetime import datetime, timezone
from typing import Optional
import os
#DB_PATH = "prism_app.sqlite"
DB_PATH = os.getenv("DB_PATH", "prism_app.sqlite")
def _conn():
    #return sqlite3.connect(DB_PATH, check_same_thread=False)
    return sqlite3.connect("prism_memory.sqlite", check_same_thread=False)
def init_db():
    conn = _conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS connected_repos (
            owner TEXT, repo TEXT, webhook_id INTEGER, notify_email TEXT,github_token TEXT,
            connected_at TEXT, PRIMARY KEY (owner, repo)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            thread_id TEXT PRIMARY KEY,
            pr_url TEXT, owner TEXT, repo TEXT, pr_number INTEGER,
            trigger_source TEXT, notify_email TEXT,    -- 'manual' or 'webhook'
            status TEXT,           -- 'running' | 'awaiting_approval' | 'approved' | 'rejected'
            created_at TEXT, updated_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_commits (
            owner TEXT, repo TEXT, pr_number INTEGER, sha TEXT,
            PRIMARY KEY (owner, repo, pr_number, sha)
        )
    """)

    # --- migration: add columns that may be missing from an older on-disk DB ---
    repo_cols = [r[1] for r in conn.execute("PRAGMA table_info(connected_repos)").fetchall()]
    if "notify_email" not in repo_cols:
        conn.execute("ALTER TABLE connected_repos ADD COLUMN notify_email TEXT")
    if "github_token" not in repo_cols:
        conn.execute("ALTER TABLE connected_repos ADD COLUMN github_token TEXT")
    run_cols = [r[1] for r in conn.execute("PRAGMA table_info(runs)").fetchall()]
    if "notify_email" not in run_cols:
        conn.execute("ALTER TABLE runs ADD COLUMN notify_email TEXT")

    conn.commit()
    conn.close()

# ── connected_repos ──────────────────────────────────────────────────────────

def add_connected_repo(owner: str, repo: str, webhook_id: int, notify_email: str,github_token: str):
    conn = _conn()
    conn.execute(
        "INSERT OR REPLACE INTO connected_repos (owner, repo, webhook_id, notify_email, github_token, connected_at) VALUES (?, ?, ?, ?, ?,?)",
        (owner, repo, webhook_id, notify_email, github_token, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit(); conn.close()

def get_repo_token(owner: str, repo: str) -> Optional[str]:
    conn = _conn()
    row = conn.execute(
        "SELECT github_token FROM connected_repos WHERE owner=? AND repo=?", (owner, repo)
    ).fetchone()
    conn.close()
    return row[0] if row else None

def get_notify_email(owner, repo) -> Optional[str]:
    conn = _conn()
    row = conn.execute(
        "SELECT notify_email FROM connected_repos WHERE owner=? AND repo=?", (owner, repo)
    ).fetchone()
    conn.close()
    return row[0] if row else None

def remove_connected_repo(owner: str, repo: str):
    conn = _conn()
    conn.execute("DELETE FROM connected_repos WHERE owner=? AND repo=?", (owner, repo))
    conn.commit(); conn.close()

def list_connected_repos() -> list[dict]:
    conn = _conn()
    rows = conn.execute("SELECT owner, repo, webhook_id, connected_at FROM connected_repos").fetchall()
    conn.close()
    return [{"owner": r[0], "repo": r[1], "webhook_id": r[2], "connected_at": r[3]} for r in rows]

def get_webhook_id(owner: str, repo: str) -> Optional[int]:
    conn = _conn()
    row = conn.execute("SELECT webhook_id FROM connected_repos WHERE owner=? AND repo=?", (owner, repo)).fetchone()
    conn.close()
    return row[0] if row else None

# ── runs ──────────────────────────────────────────────────────────────────────

def create_run(thread_id: str, pr_url: str, owner: str, repo: str, pr_number: int,
                trigger_source: str, notify_email: Optional[str] = None):
    conn = _conn()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO runs "
        "(thread_id, pr_url, owner, repo, pr_number, trigger_source, notify_email, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (thread_id, pr_url, owner, repo, pr_number, trigger_source, notify_email, "running", now, now),
    )
    conn.commit(); conn.close()

def update_run_status(thread_id: str, status: str):
    conn = _conn()
    conn.execute(
        "UPDATE runs SET status=?, updated_at=? WHERE thread_id=?",
        (status, datetime.now(timezone.utc).isoformat(), thread_id),
    )
    conn.commit(); conn.close()

def list_pending_runs() -> list[dict]:
    conn = _conn()
    rows = conn.execute(
        "SELECT thread_id, pr_url, owner, repo, pr_number, trigger_source, updated_at "
        "FROM runs WHERE status='awaiting_approval' ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return [
        {"thread_id": r[0], "pr_url": r[1], "owner": r[2], "repo": r[3],
         "pr_number": r[4], "trigger_source": r[5], "updated_at": r[6]}
        for r in rows
    ]

# ── idempotency for webhook deliveries ──────────────────────────────────────

def already_processed(owner: str, repo: str, pr_number: int, sha: str) -> bool:
    conn = _conn()
    row = conn.execute(
        "SELECT 1 FROM processed_commits WHERE owner=? AND repo=? AND pr_number=? AND sha=?",
        (owner, repo, pr_number, sha),
    ).fetchone()
    conn.close()
    return row is not None

def mark_processed(owner: str, repo: str, pr_number: int, sha: str):
    conn = _conn()
    conn.execute(
        "INSERT OR IGNORE INTO processed_commits VALUES (?, ?, ?, ?)",
        (owner, repo, pr_number, sha),
    )
    conn.commit(); conn.close()