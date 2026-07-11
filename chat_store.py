"""
chat_store.py — SQLite-backed storage for repo-chat conversation history,
used to power the "resume previous chat" feature.
"""
import sqlite3
import json
import os
import time
from typing import Optional

_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "chat_sessions.db")
os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)


def _conn():
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            thread_id   TEXT PRIMARY KEY,
            repo_url    TEXT NOT NULL,
            github_user TEXT,
            title       TEXT,
            created_at  REAL,
            updated_at  REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id   TEXT NOT NULL,
            question    TEXT,
            answer_json TEXT,
            created_at  REAL
        )
    """)
    return conn


def create_session_if_missing(thread_id: str, repo_url: str, github_user: Optional[str], first_question: str):
    conn = _conn()
    now = time.time()
    title = (first_question[:60] + "…") if len(first_question) > 60 else first_question
    conn.execute(
        "INSERT OR IGNORE INTO chat_sessions (thread_id, repo_url, github_user, title, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (thread_id, repo_url, github_user, title, now, now),
    )
    conn.commit()
    conn.close()


def save_turn(thread_id: str, question: str, answer: dict):
    conn = _conn()
    now = time.time()
    conn.execute(
        "INSERT INTO chat_messages (thread_id, question, answer_json, created_at) VALUES (?, ?, ?, ?)",
        (thread_id, question, json.dumps(answer), now),
    )
    conn.execute("UPDATE chat_sessions SET updated_at = ? WHERE thread_id = ?", (now, thread_id))
    conn.commit()
    conn.close()


def list_sessions(repo_url: str, github_user: Optional[str]) -> list[dict]:
    conn = _conn()
    rows = conn.execute(
        "SELECT thread_id, title, created_at, updated_at FROM chat_sessions "
        "WHERE repo_url = ? AND (github_user = ? OR ? IS NULL) "
        "ORDER BY updated_at DESC LIMIT 30",
        (repo_url, github_user, github_user),
    ).fetchall()
    conn.close()
    return [
        {"thread_id": r[0], "title": r[1] or "Untitled chat", "created_at": r[2], "updated_at": r[3]}
        for r in rows
    ]


def get_history(thread_id: str) -> list[list]:
    conn = _conn()
    rows = conn.execute(
        "SELECT question, answer_json FROM chat_messages WHERE thread_id = ? ORDER BY id ASC",
        (thread_id,),
    ).fetchall()
    conn.close()
    return [[q, json.loads(a)] for q, a in rows]


def delete_session(thread_id: str):
    conn = _conn()
    conn.execute("DELETE FROM chat_sessions WHERE thread_id = ?", (thread_id,))
    conn.execute("DELETE FROM chat_messages WHERE thread_id = ?", (thread_id,))
    conn.commit()
    conn.close()