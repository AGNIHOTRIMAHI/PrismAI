"""
pages/Chat.py
Full-page CRAG chat interface for PrismAI.
Reads repo context from session state set by the main dashboard.
"""
import uuid
import requests
import streamlit as st

st.set_page_config(
    page_title="PrismAI · Repo Chat",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="collapsed",
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
repo_url     = st.session_state.get("chat_repo_url", "")
github_token = st.session_state.get("chat_github_token", "")

# ── Session state ─────────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "chat_thread_id" not in st.session_state:
    st.session_state.chat_thread_id = str(uuid.uuid4())

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Kavoon&family=Roboto+Mono:wght@400;700&display=swap');

.stApp {{
    background-color: {bg_color};
    color: {text_color};
}}

/* Hide default streamlit header/footer */
#MainMenu, footer, header {{ visibility: hidden; }}

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
        resp = requests.post(
            f"{BACKEND_URL}/chat/repo",
            json={
                "repo_url": repo_url,
                "question": question,
                "history": st.session_state.chat_history,
                "github_token": github_token or None,
                "thread_id": st.session_state.chat_thread_id,
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
back_col, title_col, clear_col = st.columns([1, 8, 1])

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

with clear_col:
    if st.button("🗑 Clear", key="clear_btn"):
        st.session_state.chat_history = []
        st.session_state.chat_thread_id = str(uuid.uuid4())
        st.rerun()

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
    # User bubble
    st.markdown(f"""
    <div class="msg-wrap-user">
        <div class="bubble-user">{user_msg}</div>
    </div>
    """, unsafe_allow_html=True)

    # Bot bubble
    if isinstance(bot_data, dict):
        answer  = bot_data.get("answer", "")
        sources = bot_data.get("sources", [])
        web     = bot_data.get("crag_triggered_web_search", False)
        score   = bot_data.get("crag_relevance_score", 0)

        badge = (
            '<span class="crag-badge-web">🌐 Web-augmented</span>'
            if web else
            f'<span class="crag-badge-repo">📁 Repo context · {score:.0%} relevance</span>'
        )
        src_html = ""
        if sources:
            src_html = '<div class="sources-line">📎 ' + " · ".join(f"<code>{s}</code>" for s in sources[:5]) + "</div>"

        st.markdown(f"""
        <div class="msg-wrap-bot">
            <div class="bubble-bot">
                {answer}
                {src_html}
                {badge}
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="msg-wrap-bot">
            <div class="bubble-bot">{bot_data}</div>
        </div>
        """, unsafe_allow_html=True)

# Add some padding so the last message isn't hidden behind the input bar
st.markdown("<div style='height:80px'></div>", unsafe_allow_html=True)

# ── Native Input bar (Automatically Pinned to Bottom) ────────────────────────
if prompt := st.chat_input("Ask anything about this repo..."):
    if not repo_url:
        st.warning("⚠️ No repo loaded. Go back to the dashboard and load a PR first.")
    else:
        with st.spinner("CRAG thinking…"):
            result = ask_backend(prompt.strip())
        st.session_state.chat_history.append([prompt.strip(), result])
        st.rerun()