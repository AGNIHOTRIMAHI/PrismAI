"""
pages/Chat.py
Full-page CRAG chat interface for PrismAI.
Reads repo context from session state set by the main dashboard.
"""
import uuid
import requests
import streamlit as st
from datetime import datetime

def format_ts(epoch) -> str:
    try:
        return datetime.fromtimestamp(epoch).strftime("%b %d, %I:%M %p")
    except Exception:
        return ""


st.set_page_config(
    page_title="PrismAI · Repo Chat",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Pull theme + repo context from session state ─────────────────────────────
bg_color     = "#080212"
panel_bg     = "#250a47"
border_color = "#54199c"
text_color   = "#e4e4e7"
title_color  = "#f4f4f5"
btn_bg       = "#9d4edd"
btn_hover    = "#b5179e"
shadow_color = "rgba(157,78,221,0.7)"

BACKEND_URL  = st.session_state.get("chat_backend_url", "https://prismai-backend-nih2.onrender.com")
#BACKEND_URL  = st.session_state.get("chat_backend_url", "http://localhost:8000")
repo_url     = st.session_state.get("chat_repo_url", "")
github_token = st.session_state.get("chat_github_token", "")

# ── Session state ─────────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "chat_thread_id" not in st.session_state:
    st.session_state.chat_thread_id = str(uuid.uuid4())


# ── Fetch and offer previous conversations for this repo ────────────────────

# ── Sidebar: chat controls ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 💬 Chats")

    github_user = st.session_state.get("github_user", {})
    github_login = github_user.get("login") if isinstance(github_user, dict) else None

    _debug_error = None
    if repo_url:
        try:
            threads_resp = requests.get(
                f"{BACKEND_URL}/chat/threads",
                params={"repo_url": repo_url, "github_user": github_login},
                timeout=10,
            )
            past_threads = threads_resp.json() if threads_resp.status_code == 200 else []
        except Exception as e:
            past_threads = []
            _debug_error = e
    else:
        past_threads = []

    if past_threads:
        options = {"— Start new chat —": None}
        for t in past_threads:
            short_title = t['title'][:28] + "…" if len(t['title']) > 28 else t['title']
            options[f"{short_title} · {format_ts(t.get('updated_at'))}"] = t["thread_id"]

        chosen_label = st.selectbox("Resume a previous chat", list(options.keys()), key="resume_picker")
        chosen_thread_id = options[chosen_label]

        if chosen_thread_id and chosen_thread_id != st.session_state.chat_thread_id:
            try:
                hist_resp = requests.get(f"{BACKEND_URL}/chat/history/{chosen_thread_id}", timeout=10)
                if hist_resp.status_code == 200:
                    st.session_state.chat_history = hist_resp.json()
                    st.session_state.chat_thread_id = chosen_thread_id
                    st.rerun()
            except Exception as e:
                st.warning(f"Couldn't load that chat: {e}")

    if st.button("+ New", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.chat_thread_id = str(uuid.uuid4())
        st.rerun()

    if st.button("🗑 Clear", use_container_width=True, key="clear_btn"):
        st.session_state.chat_history = []
        st.session_state.chat_thread_id = str(uuid.uuid4())
        st.rerun()

    with st.expander("Debug Info"):
        st.json(past_threads)
        if _debug_error:
            st.write("exception:", _debug_error)





# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Kavoon&family=Roboto+Mono:wght@400;700&display=swap');

.stApp {{
    background-color: {bg_color};
    color: {text_color};
}}



/* Hide only the specific menu (⋮) and Deploy button icons inside the
   toolbar — do NOT hide the whole toolbar, since the sidebar's
   expand/collapse control can live inside it depending on version. */
#MainMenu, footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stAppDeployButton"] {{ display: none !important; }}

/* Match ANY element whose data-testid contains "ollaps" (covers
   stSidebarCollapsedControl, collapsedControl, stSidebarCollapseButton,
   etc. across Streamlit versions) and force it visible + on top. */
[data-testid*="ollaps" i] {{
    visibility: visible !important;
    display: flex !important;
    opacity: 1 !important;
    position: fixed !important;
    top: 12px !important;
    left: 12px !important;
    z-index: 999999 !important;
    background: {panel_bg} !important;
    border: 1px solid {border_color} !important;
    border-radius: 8px !important;
}}



.chat-page-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px 0 12px 0;
    border-bottom: 1px solid {border_color};
    margin-bottom: 20px;
}}
.chat-page-title {{
    font-family: 'Kavoon', cursive;
    font-size: 1.6rem;
    color: {title_color};
    letter-spacing: 1px;
}}
.chat-repo-badge {{
    font-family: 'Roboto Mono', monospace;
    font-size: 11px;
    color: {btn_bg};
    border: 1px solid {border_color};
    border-radius: 12px;
    padding: 3px 12px;
    background: rgba(157,78,221,0.1);
    word-break: break-all;
}}
.crag-badge-web {{
    display: inline-block;
    font-size: 10px;
    font-family: 'Roboto Mono', monospace;
    padding: 2px 8px;
    border-radius: 8px;
    background: rgba(245,158,11,0.15);
    color: #f59e0b;
    border: 1px solid #f59e0b44;
    margin-top: 6px;
}}
.crag-badge-repo {{
    display: inline-block;
    font-size: 10px;
    font-family: 'Roboto Mono', monospace;
    padding: 2px 8px;
    border-radius: 8px;
    background: rgba(16,185,129,0.15);
    color: #10b981;
    border: 1px solid #10b98144;
    margin-top: 6px;
}}
.sources-line {{
    font-size: 11px;
    font-family: 'Roboto Mono', monospace;
    color: {btn_bg};
    margin-top: 5px;
    opacity: 0.85;
}}

/* Message bubbles */
.msg-wrap-user {{
    display: flex;
    justify-content: flex-end;
    margin-bottom: 14px;
}}
.msg-wrap-bot {{
    display: flex;
    justify-content: flex-start;
    margin-bottom: 14px;
}}
.bubble-user {{
    background: {btn_bg};
    color: #fff;
    padding: 11px 16px;
    border-radius: 18px 18px 4px 18px;
    max-width: 70%;
    font-size: 0.93rem;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    line-height: 1.55;
    word-break: break-word;
}}
.bubble-bot {{
    background: {panel_bg};
    color: {text_color};
    padding: 11px 16px;
    border-radius: 18px 18px 18px 4px;
    max-width: 72%;
    font-size: 0.93rem;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    line-height: 1.55;
    border: 1px solid {border_color};
    word-break: break-word;
}}
.chat-empty-state {{
    text-align: center;
    padding: 60px 20px;
    color: rgba(255,255,255,0.25);
    font-family: 'Roboto Mono', monospace;
    font-size: 0.9rem;
}}
.chat-empty-state .icon {{
    font-size: 2.5rem;
    margin-bottom: 12px;
}}

button[data-testid="stBaseButton-secondary"] {{
    background: transparent !important;
    border: 1px solid {border_color} !important;
    color: {text_color} !important;
    border-radius: 8px !important;
}}
</style>
""", unsafe_allow_html=True)

# ── Helper ────────────────────────────────────────────────────────────────────
def ask_backend(question: str) -> dict:
    try:
        # Safely extract answer string — prior turns may have stored error dicts
        def _extract_answer(bot_data) -> str:
            if isinstance(bot_data, dict):
                answer = bot_data.get("answer", "")
                # answer itself might be a stringified error — still a str, so fine
                return answer if isinstance(answer, str) else str(answer)
            return str(bot_data) if bot_data else ""

        resp = requests.post(
            f"{BACKEND_URL}/chat/repo",
            json={
                "repo_url": repo_url,
                "question": question,
                "history": [
                    [turn[0], _extract_answer(turn[1])]
                    for turn in st.session_state.chat_history
                ],
                "github_token": github_token or None,
                "thread_id": st.session_state.chat_thread_id,
                "github_user": github_login,
            },
            timeout=90,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        return {"answer": "⏱️ Timed out — the repo may be large, try again.", "sources": [], "crag_relevance_score": 0, "crag_triggered_web_search": False}
    except Exception as e:
        return {"answer": f"❌ Error: {e}", "sources": [], "crag_relevance_score": 0, "crag_triggered_web_search": False}
    



# ── Header ────────────────────────────────────────────────────────────────────
back_col, title_col = st.columns([1, 9])

with back_col:
    if st.button("← Back", key="back_btn"):
        st.switch_page("app.py")

with title_col:
    st.markdown(f"""
    <div class="chat-page-header">
        <div>
            <div class="chat-page-title">💬 Repo Chat</div>
            <div style="font-family:'Roboto Mono',monospace; font-size:11px; color:{btn_bg}; margin-top:4px;">
                CRAG · LangGraph · MemorySaver
            </div>
        </div>
        <div class="chat-repo-badge">
            {'📁 ' + repo_url if repo_url else '⚠️ No repo loaded — go back and load a PR first'}
        </div>
    </div>
    """, unsafe_allow_html=True)


# ── Suggested questions ───────────────────────────────────────────────────────
if not st.session_state.chat_history:
    st.markdown(f"""
    <div class="chat-empty-state">
        <div class="icon">🔮</div>
        Ask anything about the repository.<br><br>
        <span style="color:rgba(255,255,255,0.4);">Try one of these:</span>
    </div>
    """, unsafe_allow_html=True)

    suggestions = [
        "How does the security agent work?",
        "Explain the LangGraph pipeline flow",
        "What does the CRAG node do?",
        "How is the GitHub diff fetched?",
    ]
    s_cols = st.columns(len(suggestions))
    for i, (col, q) in enumerate(zip(s_cols, suggestions)):
        with col:
            if st.button(q, key=f"suggest_{i}", use_container_width=True):
                with st.spinner("Thinking…"):
                    result = ask_backend(q)
                st.session_state.chat_history.append([q, result])
                st.rerun()


# ── Chat messages ─────────────────────────────────────────────────────────────
for user_msg, bot_data in st.session_state.chat_history:
    with st.chat_message("user"):
        st.markdown(user_msg)

    with st.chat_message("assistant"):
        if isinstance(bot_data, dict):
            answer  = bot_data.get("answer", "")
            sources = bot_data.get("sources", [])
            web     = bot_data.get("crag_triggered_web_search", False)
            score   = bot_data.get("crag_relevance_score", 0)

            st.markdown(answer)

            if sources:
                st.caption("📎 " + " · ".join(f"`{s}`" for s in sources[:5]))

            if web:
                st.markdown('<span class="crag-badge-web">🌐 Web-augmented</span>', unsafe_allow_html=True)
            else:
                st.markdown(f'<span class="crag-badge-repo">📁 Repo context · {score:.0%} relevance</span>', unsafe_allow_html=True)
        else:
            st.markdown(str(bot_data))




# ── Native Input bar (Automatically Pinned to Bottom) ────────────────────────
if prompt := st.chat_input("Ask anything about this repo..."):
    if not repo_url:
        st.warning("⚠️ No repo loaded. Go back to the dashboard and load a PR first.")
    else:
        with st.spinner("CRAG thinking…"):
            result = ask_backend(prompt.strip())
        st.session_state.chat_history.append([prompt.strip(), result])
        st.rerun()