import streamlit as st
import requests
import uuid
import time
import threading
import uvicorn
import json
import base64
from auth import init_auth_state, check_login_status, is_logged_in, render_landing_page, render_user_header_widget
from chat_with_repo import render_chat_widget
# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & CSS (Must be first)
# -----------------------------------------------------------------------------
st.set_page_config(page_title="PrismAI", page_icon="🟪", layout="wide")

if "light_mode" not in st.session_state:
    st.session_state.light_mode = False

# -----------------------------------------------------------------------------
# 2. DYNAMIC CSS (Swaps based on toggle)
# -----------------------------------------------------------------------------
if st.session_state.light_mode:
    # --- ☀️ LIGHT MODE PALETTE ---
    bg_color = "#f7f2fc"          
    text_color = "#401371"        
    panel_bg = "#ffffff"          
    border_color = "#cfa1ed"      
    shadow_color = "rgba(157,78,221,0.2)"
    title_color = "#552E7E"
    btn_bg = "#7b2cbf"
    btn_hover = "#9d4edd"
else:
    # --- 🌙 DARK MODE PALETTE ---
    bg_color = "#080212"          
    text_color = "#e4e4e7"        
    panel_bg = "#250a47"          
    border_color = "#54199c"      
    shadow_color = "rgba(157,78,221,0.7)"
    title_color = "#f4f4f5"
    btn_bg = "#9d4edd"            
    btn_hover = "#b5179e"

# FIX: Added the 'f' right before the quotes so Python injects the color variables properly!
st.markdown(f"""
<style>
    /* Import Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Amita:wght@400;700&family=Italiana&family=Josefin+Sans:ital,wght@0,100..700;1,100..700&family=Kavoon&family=Lora:ital,wght@0,400..700;1,400..700&family=Merienda:wght@300..900&family=Merriweather:ital,opsz,wght@0,18..144,300..900;1,18..144,300..900&family=Poppins:ital,wght@0,100;0,200;0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,100;1,200;1,300;1,400;1,500;1,600;1,700;1,800;1,900&family=Roboto+Mono:ital,wght@0,100..700;1,100..700&family=Roboto:ital,wght@0,100..900;1,100..900&family=Satisfy&family=Ubuntu:ital,wght@0,300;0,400;0,500;0,700;1,300;1,400;1,500;1,700&display=swap');
    
    .kavoon-title {{
        font-family: 'Kavoon', cursive !important;
        font-size: 2.5rem !important;
        color: {title_color} !important;
        line-height: 1 !important;
        margin: 0 !important;
        padding: 0 !important;
        letter-spacing: 1px !important;
        transition: color 0.3s ease;
    }}

    /* Global App Colors */
    .stApp {{ background-color: {bg_color}; color: {text_color}; transition: background-color 0.3s ease; }}
    h2, h3, p, span, div {{ color: {text_color} !important; }}
    h2, h3 {{ font-family: 'Courier New', monospace; }}
    
    /* Inputs & Selectboxes */
   /* 1. Global Reset for ALL input container wrappers */
    .stTextInput > div, 
    div[data-baseweb="input"] ,
    div[data-baseweb="base-input"] {{
        background-color: {panel_bg} !important;
        border: 1px solid {border_color} !important;
        transition: all 0.2s ease-in-out !important;
    }}

    /* 2. Target the actual input text field */
    .stTextInput>div>div>input {{ 
        background-color: transparent !important; 
        color: {text_color} !important; 
        border: none !important; /* Removes internal extra borders */
    }}
    
    .stSelectbox>div>div>div {{ 
        background-color: {panel_bg} !important; 
        color: {text_color} !important; 
        border: 1px solid {border_color} !important; 
    }}
    
    /* 3. FIX: Catch the parent container when focused from inside */
    .stTextInput > div:focus-within,
    div[data-baseweb="input"]:focus-within ,
    div[data-baseweb="base-input"]:focus-within{{
        border-color: #9d4edd !important; /* Force vibrant purple */
        box-shadow:inset 0 0 10px {shadow_color}, 0 0 8px {shadow_color} !important; /* Glow effect */
    }}

    /* Remove Streamlit's secondary default outline entirely */
    .stTextInput > div:focus-within input {{
        outline: none !important;
        border: none !important;
        background-color: transparent !important;
    }}
    /* Custom Circular Theme Toggle Button */
    button[kind="secondary"] {{
        border-radius: 50% !important;
        width: 48px !important;
        height: 48px !important;
        padding: 0 !important;
        font-size: 1.6rem !important;
        background-color: {panel_bg};
        border: 2px solid {border_color};
        color: {text_color};
        float: right;
        transition: all 0.3s ease;
    }}
    button[kind="secondary"]:hover {{
        border-color: #9d4edd !important;
        box-shadow: 0 0 10px {shadow_color} !important;
    }}

    /* Custom Primary Run Button Styling */
    button[data-testid="stBaseButton-primary"] {{
        background-color: {btn_bg} !important;
        color: #ffffff !important;
        border: none !important;
        font-weight: bold !important;
        transition: all 0.3s ease !important;
    }}
    
    button[data-testid="stBaseButton-primary"]:hover {{
        background-color: {btn_hover} !important;
        box-shadow: 0 0 12px {shadow_color} !important;
        transform: translateY(-1px);
    }}
    
    button[data-testid="stBaseButton-primary"]:active {{
        transform: translateY(1px);
    }}
    /* Pipeline Step Box */
    .pipe-step {{ background: {panel_bg}; border: 1px solid {border_color}; padding: 10px; border-radius: 8px; margin-bottom: 8px; font-family: monospace; transition: all 0.3s ease; }}
    .pipe-active {{ border-color: #9d4edd !important; box-shadow: 0 0 10px {shadow_color}; }}
    
    /* Adjust Streamlit Container Borders */
    [data-testid="stVerticalBlockBorderWrapper"] {{ border-color: {border_color} !important; }}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. START FASTAPI IN BACKGROUND (Local Testing Trick)
# -----------------------------------------------------------------------------
#def start_backend():
#    uvicorn.run("main:app", host="127.0.0.1", port=8000, log_level="warning")

#if "backend_started" not in st.session_state:
#    threading.Thread(target=start_backend, daemon=True).start()
#    st.session_state["backend_started"] = True
#    time.sleep(2) 

#BACKEND_URL = "http://localhost:8000"
# -----------------------------------------------------------------------------
# 2. CONNECT TO CLOUD BACKEND
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# AUTH GATE
# -----------------------------------------------------------------------------
init_auth_state()
check_login_status()

if not is_logged_in():
    render_landing_page({
        "bg_color": bg_color,
        "text_color": text_color,
        "panel_bg": panel_bg,
        "border_color": border_color,
        "shadow_color": shadow_color,
        "title_color": title_color,
        "btn_bg": btn_bg,
    })
    st.stop()

with st.sidebar:
   render_user_header_widget({
        "border_color": border_color,
        "text_color": text_color
    })

# --- SAFE CHAT ICON LOADING ---
try:
    with open("assets/chat_logo.png", "rb") as img_file:
        b64_string = base64.b64encode(img_file.read()).decode().replace('\n', '')
    my_local_icon = f"data:image/png;base64,{b64_string}"
except FileNotFoundError:
    # Fallback to a web image so the app never crashes
    my_local_icon = "https://cdn-icons-png.flaticon.com/512/8618/8618881.png"

BACKEND_URL = "https://prismai-backend-nih2.onrender.com"

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
# --- SAFE CHAT ICON LOADING ---
try:

    local_image_path = "assets/logo.jpeg"

    with open(local_image_path, "rb") as image_file:

        encoded_string = base64.b64encode(image_file.read()).decode()

    logo_url = f"data:image/jpeg;base64,{encoded_string}"

except FileNotFoundError:

    logo_url = "https://cdn-icons-png.flaticon.com/512/8618/8618881.png"

head_col1, head_col2 = st.columns([15, 1])

with head_col1:
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 18px; margin-bottom: 10px;">
        <img src="{logo_url}" width="65" style="border-radius: 12px; filter: drop-shadow(0 0 8px {shadow_color});">
        <span class="kavoon-title">PrismAI</span>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("`LangGraph v3` · `CRAG` · `HITL Multi-Agent`")

with head_col2:
    # Custom Circular Toggle Switch Logic
    # In dark mode, show a sun to switch to light mode. In light mode, show a moon.
    toggle_icon = "🌙" if st.session_state.light_mode else "☀️"
    
    if st.button(toggle_icon, key="theme_toggle"):
        st.session_state.light_mode = not st.session_state.light_mode
        st.rerun()

with st.container(border=True):
    col1, col2 = st.columns([4, 1])
    with col1:
        pr_url = st.text_input("GitHub PR URL", value="https://github.com/ABC/PrismAI/pull/1", label_visibility="collapsed")
        # --- NEW: Added token input field ---
        user_token = st.text_input("GitHub Token (Optional for Private Repos)", type="password", placeholder="ghp_...")
    with col2:
        st.write("") # Adds a little spacing to align the button nicely
        if st.button("🚀 Run Graph", use_container_width=True, type="primary"):
            st.session_state.thread_id = str(uuid.uuid4()) 
            
            with st.spinner("Triggering Pipeline..."):
                try:
                    # --- NEW: Added github_token to the JSON payload sent to the backend ---
                    payload = {
                        "pr_url": pr_url, 
                        "thread_id": st.session_state.thread_id,
                        "github_token": user_token
                    }
                    res = requests.post(f"{BACKEND_URL}/review", json=payload)
                    
                    if res.status_code == 200:
                        st.session_state.is_polling = True
                    else:
                        st.error(f"Backend Error: {res.text}")
                except Exception as e:
                    st.error(f"Connection Failed: {e}")
            st.rerun()
# -----------------------------------------------------------------------------
# 5. POLLING LOGIC
# -----------------------------------------------------------------------------
if st.session_state.is_polling:
    try:
        res = requests.get(f"{BACKEND_URL}/state/{st.session_state.thread_id}")
        if res.status_code == 200:
            data = res.json()
            st.session_state.graph_state = data
            
            if data.get("waiting_for_human") or data.get("done"):
                st.session_state.is_polling = False
            else:
                time.sleep(2) 
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
                    is_approved = True if decision == "Approve Merge" else False
                    
                    try:
                        post_res = requests.post(f"{BACKEND_URL}/approve", json={
                            "thread_id": st.session_state.thread_id,
                            "approved": is_approved
                        })
                        if post_res.status_code == 200:
                            st.success("Decision Transmitted! Resuming pipeline...")
                            st.session_state.is_polling = True 
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Failed to submit: {post_res.text}")
                    except Exception as e:
                        st.error(f"API Error: {e}")

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

render_chat_widget(   
    icon_url=my_local_icon,
    backend_url=BACKEND_URL,
    btn_bg=btn_bg,
    shadow_color=shadow_color,
    repo_url=pr_url,
    github_token=user_token,
)