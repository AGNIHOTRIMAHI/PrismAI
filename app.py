import streamlit as st
import requests
import uuid
import time
import threading
import uvicorn
import json

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & CSS (Must be first)
# -----------------------------------------------------------------------------
st.set_page_config(page_title="OpsSphere PR Console", page_icon="🛡️", layout="wide")

st.markdown("""
<style>
    /* Ops Console Dark Theme Overrides */
    .stApp { background-color: #09090b; color: #e4e4e7; }
    h1, h2, h3 { color: #f4f4f5 !important; font-family: 'Courier New', monospace; }
    .stTextInput>div>div>input { background-color: #18181b; color: #a1a1aa; border: 1px solid #27272a; }
    .stSelectbox>div>div>div { background-color: #18181b; color: #a1a1aa; border: 1px solid #27272a; }
    
    /* Custom Badges */
    .badge-running { background: rgba(59,130,246,0.1); color: #3b82f6; border: 1px solid #3b82f6; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-family: monospace; }
    .badge-done { background: rgba(16,185,129,0.1); color: #10b981; border: 1px solid #10b981; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-family: monospace; }
    .badge-hitl { background: rgba(245,158,11,0.1); color: #f59e0b; border: 1px solid #f59e0b; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-family: monospace; }
    
    /* Pipeline Step Box */
    .pipe-step { background: #18181b; border: 1px solid #27272a; padding: 10px; border-radius: 8px; margin-bottom: 8px; font-family: monospace; }
    .pipe-active { border-color: #3b82f6; box-shadow: 0 0 8px rgba(59,130,246,0.3); }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. START FASTAPI IN BACKGROUND (Local Testing Trick)
# -----------------------------------------------------------------------------
def start_backend():
    uvicorn.run("main:app", host="127.0.0.1", port=8000, log_level="warning")

if "backend_started" not in st.session_state:
    threading.Thread(target=start_backend, daemon=True).start()
    st.session_state["backend_started"] = True
    time.sleep(2) # Give the server a second to spin up

BACKEND_URL = "http://localhost:8000"

# -----------------------------------------------------------------------------
# 3. SESSION STATE MANAGEMENT
# -----------------------------------------------------------------------------
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "is_polling" not in st.session_state:
    st.session_state.is_polling = False
if "graph_state" not in st.session_state:
    st.session_state.graph_state = {}

# -----------------------------------------------------------------------------
# 4. UI HEADER & TRIGGER
# -----------------------------------------------------------------------------
st.title("🛡️ OpsSphere PR Console")
st.markdown("`LangGraph v3` · `CRAG` · `HITL Multi-Agent`")

with st.container(border=True):
    col1, col2 = st.columns([4, 1])
    with col1:
        pr_url = st.text_input("GitHub PR URL", value="https://github.com/AGNIHOTRIMAHI/OpsSphere/pull/1", label_visibility="collapsed")
    with col2:
        if st.button("🚀 Run Graph", use_container_width=True, type="primary"):
            st.session_state.thread_id = str(uuid.uuid4()) # Generate new thread for new run
            
            with st.spinner("Triggering Pipeline..."):
                try:
                    res = requests.post(f"{BACKEND_URL}/review", json={"pr_url": pr_url, "thread_id": st.session_state.thread_id})
                    if res.status_code == 200:
                        st.session_state.is_polling = True
                    else:
                        st.error(f"Backend Error: {res.text}")
                except Exception as e:
                    st.error(f"Connection Failed: {e}")
            st.rerun()

# -----------------------------------------------------------------------------
# 5. POLLING LOGIC (Syncs Streamlit with FastAPI)
# -----------------------------------------------------------------------------
if st.session_state.is_polling:
    try:
        res = requests.get(f"{BACKEND_URL}/state/{st.session_state.thread_id}")
        if res.status_code == 200:
            data = res.json()
            st.session_state.graph_state = data
            
            # Stop polling if we hit HITL or if the graph is completely done
            if data.get("waiting_for_human") or data.get("done"):
                st.session_state.is_polling = False
            else:
                time.sleep(2) # Wait 2 seconds before checking again
                st.rerun()
    except Exception as e:
        st.error(f"Polling lost connection to server: {e}")
        st.session_state.is_polling = False

# -----------------------------------------------------------------------------
# 6. MAIN DASHBOARD UI
# -----------------------------------------------------------------------------
state_data = st.session_state.graph_state
values = state_data.get("values", {})
is_waiting = state_data.get("waiting_for_human", False)
is_done = state_data.get("done", False)

col_left, col_right = st.columns([1, 2])

# --- LEFT COLUMN: PIPELINE STATUS ---
with col_left:
    st.markdown("### Pipeline State")
    
    # Simple logic to light up steps based on what data exists in the state
    has_diff = "code_diff" in values
    has_sec = "security_feedback" in values
    has_crag = "crag_context" in values
    
    st.markdown(f"<div class='pipe-step {'pipe-active' if has_diff and not has_sec else ''}'>1. Fetcher Node {'✅' if has_diff else '⏳'}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='pipe-step {'pipe-active' if has_sec and not has_crag else ''}'>2. Security & Style Agents {'✅' if has_sec else '⏳'}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='pipe-step {'pipe-active' if has_crag and not is_waiting and not is_done else ''}'>3. CRAG Evaluator {'✅' if has_crag else '⏳'}</div>", unsafe_allow_html=True)
    
    if is_waiting:
        st.markdown("<div class='pipe-step pipe-active' style='border-color: #f59e0b;'>4. HITL Breakpoint (BLOCKED) ⚠️</div>", unsafe_allow_html=True)
    elif is_done:
        st.markdown("<div class='pipe-step' style='border-color: #10b981;'>4. Completed ✅</div>", unsafe_allow_html=True)

    if values:
        with st.expander("Raw State Dump"):
            st.json(values)

# --- RIGHT COLUMN: REPORTS & HITL DECISION CENTER ---
with col_right:
    # 1. Show the Decision Center if waiting for human
    if is_waiting:
        st.markdown("### 🚨 Decision Center")
        st.error("Pipeline Paused: Awaiting Senior Engineer authorization.")
        
        with st.form("hitl_form"):
            st.markdown(f"**Thread ID:** `{st.session_state.thread_id}`")
            
            decision = st.selectbox("Action", ["Approve Merge", "Reject / Drop Request"])
            reviewer = st.text_input("Reviewer ID", placeholder="e.g. ops-admin")
            
            if st.form_submit_button("Transmit Decision", type="primary"):
                if not reviewer:
                    st.warning("Reviewer ID is required.")
                else:
                    # Map the UI choice to the boolean expected by your FastAPI endpoint
                    is_approved = True if decision == "Approve Merge" else False
                    
                    try:
                        post_res = requests.post(f"{BACKEND_URL}/approve", json={
                            "thread_id": st.session_state.thread_id,
                            "approved": is_approved
                        })
                        if post_res.status_code == 200:
                            st.success("Decision Transmitted! Resuming pipeline...")
                            st.session_state.is_polling = True # Start watching the server again
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Failed to submit: {post_res.text}")
                    except Exception as e:
                        st.error(f"API Error: {e}")

    # 2. Show the Agent Reports
    st.markdown("### Agent Reports")
    if not values:
        st.info("Awaiting pipeline execution...")
    else:
        if "security_feedback" in values:
            with st.container(border=True):
                st.markdown("**🛡️ Security Agent**")
                st.markdown(values["security_feedback"])
        
        if "style_feedback" in values:
            with st.container(border=True):
                st.markdown("**⚡ Style & Performance Agent**")
                st.markdown(values["style_feedback"])
                
        if "crag_context" in values:
            with st.container(border=True):
                st.markdown("**🔍 CRAG Grounding Evaluator**")
                st.markdown(values["crag_context"])

        if "final_status" in values:
            st.success(values["final_status"])