import streamlit as st
import requests
import uuid
import time
import base64
from auth import init_auth_state, check_login_status, is_logged_in, render_landing_page, render_user_header_widget
from chat_with_repo import render_chat_widget

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(page_title="PrismAI", page_icon="🟪", layout="wide")

if "light_mode" not in st.session_state:
    st.session_state.light_mode = False

# -----------------------------------------------------------------------------
# 2. DYNAMIC CSS
# -----------------------------------------------------------------------------
if st.session_state.light_mode:
    bg_color     = "#f7f2fc";  text_color   = "#401371";  panel_bg     = "#ffffff"
    border_color = "#cfa1ed";  shadow_color = "rgba(157,78,221,0.2)"
    title_color  = "#552E7E";  btn_bg       = "#7b2cbf";  btn_hover    = "#9d4edd"
else:
    bg_color     = "#080212";  text_color   = "#e4e4e7";  panel_bg     = "#250a47"
    border_color = "#54199c";  shadow_color = "rgba(157,78,221,0.7)"
    title_color  = "#f4f4f5";  btn_bg       = "#9d4edd";  btn_hover    = "#b5179e"

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Kavoon&family=Poppins:wght@400;500;600&display=swap');
    .kavoon-title {{
        font-family:'Kavoon',cursive !important; font-size:2.5rem !important;
        color:{title_color} !important; line-height:1 !important;
        margin:0 !important; padding:0 !important; letter-spacing:1px !important;
    }}
    .stApp {{ background-color:{bg_color}; color:{text_color}; }}
    h2,h3,p,span,div {{ color:{text_color} !important; }}
    h2,h3 {{ font-family:'Courier New',monospace; }}
    .stTextInput>div, div[data-baseweb="input"], div[data-baseweb="base-input"] {{
        background-color:{panel_bg} !important; border:1px solid {border_color} !important;
    }}
    .stTextInput>div>div>input {{ background-color:transparent !important; color:{text_color} !important; border:none !important; }}
    .stSelectbox>div>div>div {{ background-color:{panel_bg} !important; color:{text_color} !important; border:1px solid {border_color} !important; }}
    .stTextInput>div:focus-within, div[data-baseweb="input"]:focus-within {{
        border-color:#9d4edd !important;
        box-shadow:inset 0 0 10px {shadow_color},0 0 8px {shadow_color} !important;
    }}
    button[kind="secondary"] {{
        border-radius:50% !important; width:48px !important; height:48px !important;
        padding:0 !important; font-size:1.6rem !important;
        background-color:{panel_bg}; border:2px solid {border_color}; color:{text_color}; float:right;
    }}
    button[data-testid="stBaseButton-primary"] {{
        background-color:{btn_bg} !important; color:#fff !important;
        border:none !important; font-weight:bold !important;
    }}
    button[data-testid="stBaseButton-primary"]:hover {{
        background-color:{btn_hover} !important; box-shadow:0 0 12px {shadow_color} !important;
    }}
    .pipe-step {{
        background:{panel_bg}; border:1px solid {border_color};
        padding:10px; border-radius:8px; margin-bottom:8px; font-family:monospace;
    }}
    .pipe-active {{ border-color:#9d4edd !important; box-shadow:0 0 10px {shadow_color}; }}
    [data-testid="stVerticalBlockBorderWrapper"] {{ border-color:{border_color} !important; }}

    /* TOP LOADING BAR */
    .prism-topbar {{
        position:fixed; top:0; left:0; right:0; height:3px; z-index:99998;
        background:linear-gradient(90deg,
            transparent 0%, #9d4edd 20%, #fbbf24 50%, #9d4edd 80%, transparent 100%);
        background-size:200% 100%;
        animation:topbarSlide 1.4s ease-in-out infinite;
        box-shadow: 0 0 8px #fbbf24, 0 0 2px #9d4edd;
    }}
    @keyframes topbarSlide {{
        0%   {{ background-position: 200% 0; }}
        100% {{ background-position: -200% 0; }}
    }}

    /* REPORT CARDS */
    .report-card {{
        background: linear-gradient(145deg, {panel_bg}, #1a0835);
        border: 1px solid {border_color};
        border-radius: 12px;
        margin-bottom: 16px;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(157,78,221,0.15);
    }}
    .report-card-header {{
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 12px 16px;
        background: rgba(157,78,221,0.12);
        border-bottom: 1px solid {border_color};
        font-weight: 600;
        font-size: 13px;
        letter-spacing: 0.3px;
        color: #c084fc !important;
    }}
    .report-card-body {{
        height: 240px;
        overflow-y: auto;
        padding: 16px 18px;
        font-size: 13px;
        line-height: 1.75;
        color: {text_color} !important;
        scrollbar-width: thin;
        scrollbar-color: #54199c transparent;
    }}
    .report-card-body::-webkit-scrollbar {{ width: 5px; }}
    .report-card-body::-webkit-scrollbar-track {{ background: transparent; }}
    .report-card-body::-webkit-scrollbar-thumb {{
        background: #54199c; border-radius: 10px;
    }}
    .report-card-body p, .report-card-body li,
    .report-card-body span, .report-card-body div {{
        color: {text_color} !important;
    }}
    .report-card-body h1,.report-card-body h2,
    .report-card-body h3,.report-card-body h4 {{
        color: #c084fc !important; margin-top:10px; margin-bottom:4px;
    }}
    .report-card-body code {{
        background: rgba(157,78,221,0.2);
        padding: 1px 5px; border-radius: 4px;
        font-size: 12px; color: #34d399 !important;
    }}
    .report-card-body strong {{ color: #fbbf24 !important; }}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# LOADER
# -----------------------------------------------------------------------------
LOADER_STAGES = [
    ("🔗", "Fetching PR diff & metadata",    "#4f46e5", "#818cf8"),
    ("🛡️", "Running security audit",          "#d97706", "#fbbf24"),
    ("🎨", "Checking code style & linting",   "#059669", "#34d399"),
    ("🧠", "CRAG evaluation & grounding",     "#7c3aed", "#c084fc"),
    ("⚖️", "Awaiting HITL decision gate",     "#f59e0b", "#fbbf24"),
]

def _pill_html(current: int) -> str:
    labels = ["Fetcher", "Security", "Style", "CRAG", "HITL"]
    out = ""
    for i, lbl in enumerate(labels):
        if i < current:    cls = "po-pill po-pill-done"
        elif i == current: cls = "po-pill po-pill-active"
        else:              cls = "po-pill"
        out += f'<span class="{cls}">{i+1}. {lbl}</span>'
    return out

def _build_loader_html(stage: int) -> str:
    icon, label, c1, c2 = LOADER_STAGES[stage]
    pills = _pill_html(stage)
    return f"""
<style>
  body {{ margin:0; padding:0; background:transparent; }}
  .po-overlay {{
      position:fixed; inset:0; z-index:99999;
      backdrop-filter:blur(10px) brightness(0.25);
      -webkit-backdrop-filter:blur(10px) brightness(0.25);
      background:rgba(4,1,12,0.72);
      display:flex; flex-direction:column; align-items:center; justify-content:center;
  }}
  /* Outer yellow rotating ring */
  .po-ring-wrap {{
      position:relative; width:240px; height:240px;
      display:flex; align-items:center; justify-content:center;
      margin-bottom:28px;
  }}
  .po-ring-wrap canvas.arc-canvas {{
      position:absolute; top:0; left:0; z-index:2;
  }}
  /* Yellow CSS border that also rotates — layered on top of canvas for thickness */
  .po-ring-border {{
      position:absolute; inset:0; border-radius:50%; z-index:1;
      background: conic-gradient(
          #fbbf24 0deg, #f59e0b 60deg, #fbbf24 120deg,
          transparent 121deg, transparent 360deg
      );
      animation: rotateBorder 1.2s linear infinite;
  }}
  .po-ring-border::after {{
      content:''; position:absolute; inset:6px;
      border-radius:50%; background:transparent;
  }}
  @keyframes rotateBorder {{ to {{ transform:rotate(360deg); }} }}

  .po-sphere-inner {{
      position:absolute;
      top:50%; left:50%;
      transform:translate(-50%,-50%);
      width:200px; height:200px;
      border-radius:50%;
      background:radial-gradient(circle at 35% 32%, #1e0845, #06010f);
      display:flex; flex-direction:column; align-items:center;
      justify-content:center; gap:8px; overflow:hidden;
      z-index:3;
  }}
  .po-icon {{
      font-size:54px; filter:drop-shadow(0 0 16px {c2});
      animation:poPop 0.4s cubic-bezier(.34,1.56,.64,1);
  }}
  @keyframes poPop {{ from{{transform:scale(0.4);opacity:0}} to{{transform:scale(1);opacity:1}} }}
  .po-icon-label {{
      font-size:11px; color:#a0a0cc; text-align:center;
      padding:0 16px; line-height:1.4; font-family:'Courier New',monospace;
  }}
  .po-status {{
      font-size:15px; color:{c2}; font-weight:700; margin-bottom:4px;
      font-family:'Courier New',monospace; letter-spacing:0.5px; text-align:center;
  }}
  .po-sub {{
      font-size:12px; color:#5a4a7a; margin-bottom:20px;
      font-family:'Courier New',monospace; text-align:center;
  }}
  .po-pills {{ display:flex; gap:8px; flex-wrap:wrap; justify-content:center; max-width:480px; }}
  .po-pill {{
      padding:5px 14px; border-radius:20px; font-size:11px;
      border:1px solid #2a1a4a; color:#4a3a6a; background:#130828; font-family:monospace;
  }}
  .po-pill-done  {{ border-color:#7c3aed !important; color:#c084fc !important; background:#2a1a4a !important; }}
  .po-pill-active {{
      border-color:#fbbf24 !important; color:#fbbf24 !important; background:#1a0e00 !important;
      box-shadow: 0 0 8px rgba(251,191,36,0.4);
  }}
</style>

<div class="po-overlay">
  <div class="po-ring-wrap">
    <div class="po-ring-border"></div>
    <canvas class="arc-canvas" id="poArc" width="240" height="240"></canvas>
    <div class="po-sphere-inner">
      <div class="po-icon">{icon}</div>
      <div class="po-icon-label">{label}</div>
    </div>
  </div>
  <div class="po-status">{label}</div>
  <div class="po-sub">Step {stage+1} of {len(LOADER_STAGES)} · agents working</div>
  <div class="po-pills">{pills}</div>
</div>

<script>
(function() {{
  const canvas = document.getElementById('poArc');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let angle = Math.random() * Math.PI * 2;
  const C1 = '{c1}', C2 = '{c2}';
  function draw() {{
    ctx.clearRect(0, 0, 240, 240);
    angle += 0.04;
    const span = Math.PI * 1.4 + Math.sin(angle * 0.3) * 0.2;
    const g = ctx.createLinearGradient(0, 0, 240, 240);
    g.addColorStop(0, C1);
    g.addColorStop(1, C2);
    ctx.beginPath();
    ctx.arc(120, 120, 112, angle, angle + span);
    ctx.strokeStyle = g;
    ctx.lineWidth = 5;
    ctx.lineCap = 'round';
    ctx.stroke();
    requestAnimationFrame(draw);
  }}
  draw();
}})();
</script>
"""

def infer_stage(values: dict) -> int:
    if "crag_enhanced_context" in values: return 4
    if "security_report" in values or "style_report" in values: return 3
    if "diff_context" in values: return 1
    return 0

# -----------------------------------------------------------------------------
# 3. BACKEND URL
# -----------------------------------------------------------------------------
BACKEND_URL = "http://localhost:8000"

# -----------------------------------------------------------------------------
# 4. AUTH GATE
# -----------------------------------------------------------------------------
init_auth_state()
check_login_status()

if not is_logged_in():
    render_landing_page({
        "bg_color": bg_color, "text_color": text_color, "panel_bg": panel_bg,
        "border_color": border_color, "shadow_color": shadow_color,
        "title_color": title_color, "btn_bg": btn_bg,
    })
    st.stop()

with st.sidebar:
    render_user_header_widget({"border_color": border_color, "text_color": text_color})

# -----------------------------------------------------------------------------
# 5. ICON LOADING
# -----------------------------------------------------------------------------
try:
    with open("assets/chat_logo.png", "rb") as f:
        b64_string = base64.b64encode(f.read()).decode().replace('\n', '')
    my_local_icon = f"data:image/png;base64,{b64_string}"
except FileNotFoundError:
    my_local_icon = "https://cdn-icons-png.flaticon.com/512/8618/8618881.png"

try:
    with open("assets/logo.jpeg", "rb") as f:
        encoded_string = base64.b64encode(f.read()).decode()
    logo_url = f"data:image/jpeg;base64,{encoded_string}"
except FileNotFoundError:
    logo_url = "https://cdn-icons-png.flaticon.com/512/8618/8618881.png"

# -----------------------------------------------------------------------------
# 6. SESSION STATE
# -----------------------------------------------------------------------------
if "phase"       not in st.session_state: st.session_state.phase       = "idle"
if "thread_id"   not in st.session_state: st.session_state.thread_id   = str(uuid.uuid4())
if "graph_state" not in st.session_state: st.session_state.graph_state = {}

# -----------------------------------------------------------------------------
# 7. HEADER
# -----------------------------------------------------------------------------
head_col1, head_col2 = st.columns([15, 1])
with head_col1:
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:18px;margin-bottom:10px;">
        <img src="{logo_url}" width="65" style="border-radius:12px;filter:drop-shadow(0 0 8px {shadow_color});">
        <span class="kavoon-title">PrismAI</span>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("`LangGraph v3` · `CRAG` · `HITL Multi-Agent`")
with head_col2:
    toggle_icon = "🌙" if st.session_state.light_mode else "☀️"
    if st.button(toggle_icon, key="theme_toggle"):
        st.session_state.light_mode = not st.session_state.light_mode
        st.rerun()

# -----------------------------------------------------------------------------
# 8. INPUT FORM
# -----------------------------------------------------------------------------
with st.container(border=True):
    col1, col2 = st.columns([4, 1])
    with col1:
        pr_url = st.text_input(
            "GitHub PR URL",
            value="https://github.com/ABC/PrismAI/pull/1",
            label_visibility="collapsed",
        )
        user_token = st.text_input(
            "GitHub Token (Optional for Private Repos)",
            type="password", placeholder="ghp_...",
        )
    with col2:
        st.write("")
        if st.button("🚀 Run Graph", use_container_width=True, type="primary"):
            st.session_state.thread_id   = str(uuid.uuid4())
            st.session_state.graph_state = {}
            try:
                res = requests.post(f"{BACKEND_URL}/review", json={
                    "pr_url": pr_url,
                    "thread_id": st.session_state.thread_id,
                    "github_token": user_token,
                })
                if res.status_code == 200:
                    st.session_state.phase = "polling"
                else:
                    st.error(f"Backend Error: {res.text}")
            except Exception as e:
                st.error(f"Connection Failed: {e}")
            st.rerun()

# =============================================================================
# 9. PHASE ROUTER
# =============================================================================
phase = st.session_state.phase

# ── POLLING ───────────────────────────────────────────────────────────────────
if phase == "polling":
    values_now = st.session_state.graph_state.get("values", {})
    stage = infer_stage(values_now)

    loader_slot = st.empty()
    loader_slot.markdown(_build_loader_html(stage), unsafe_allow_html=True)

    try:
        res = requests.get(f"{BACKEND_URL}/state/{st.session_state.thread_id}")
        if res.status_code == 200:
            data = res.json()
            st.session_state.graph_state = data
            values_now = data.get("values", {})

            agents_done = (
                "security_report"       in values_now and
                "crag_enhanced_context" in values_now
            )

            if data.get("waiting_for_human") and agents_done:
                loader_slot.empty()
                st.session_state.phase = "hitl"
                st.rerun()
            elif data.get("done"):
                loader_slot.empty()
                st.session_state.phase = "done"
                st.rerun()
            else:
                time.sleep(2)
                st.rerun()
        else:
            st.error(f"State fetch error: {res.status_code}")
            loader_slot.empty()
            st.session_state.phase = "idle"
    except Exception as e:
        st.error(f"Polling error: {e}")
        loader_slot.empty()
        st.session_state.phase = "idle"

    # render chat below loader so it's still accessible while polling
    render_chat_widget(
        icon_url=my_local_icon, backend_url=BACKEND_URL,
        btn_bg=btn_bg, shadow_color=shadow_color,
        repo_url=pr_url, github_token=user_token,
    )
    st.stop()

# ── RESUMING ──────────────────────────────────────────────────────────────────
elif phase == "resuming":
    loader_slot = st.empty()
    loader_slot.markdown(_build_loader_html(4), unsafe_allow_html=True)

    try:
        res = requests.get(f"{BACKEND_URL}/state/{st.session_state.thread_id}")
        if res.status_code == 200:
            data = res.json()
            st.session_state.graph_state = data
            if data.get("done"):
                loader_slot.empty()
                st.session_state.phase = "done"
                st.rerun()
            else:
                time.sleep(2)
                st.rerun()
        else:
            st.error(f"State fetch error: {res.status_code}")
    except Exception as e:
        st.error(f"Resume polling error: {e}")
        st.session_state.phase = "hitl"

    render_chat_widget(
        icon_url=my_local_icon, backend_url=BACKEND_URL,
        btn_bg=btn_bg, shadow_color=shadow_color,
        repo_url=pr_url, github_token=user_token,
    )
    st.stop()

# ── HITL ──────────────────────────────────────────────────────────────────────
elif phase == "hitl":
    values = st.session_state.graph_state.get("values", {})
    col_left, col_right = st.columns([1, 2])

    with col_left:
        # Pipeline state
        st.markdown("### Pipeline State")
        st.markdown(f"<div class='pipe-step'>1. Fetcher Node {'✅' if 'diff_context' in values else '⏳'}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='pipe-step'>2. Security & Style Agents {'✅' if 'security_report' in values else '⏳'}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='pipe-step'>3. CRAG Evaluator {'✅' if 'crag_enhanced_context' in values else '⏳'}</div>", unsafe_allow_html=True)
        st.markdown("<div class='pipe-step pipe-active' style='border-color:#f59e0b;'>4. HITL Breakpoint (BLOCKED) ⚠️</div>", unsafe_allow_html=True)
        if values:
            with st.expander("Raw State Dump"):
                st.json(values)

        # ── Decision Center directly below pipeline state in LEFT column ──
        st.markdown("---")
        st.markdown("### 🚨 Decision Center")
        st.error("Pipeline Paused: Awaiting Senior Engineer authorization.")
        with st.form("hitl_form"):
            st.markdown(f"**Thread ID:** `{st.session_state.thread_id}`")
            decision = st.selectbox("Action", ["Approve Merge", "Reject / Drop Request"])
            reviewer = st.text_input("Reviewer ID", placeholder="e.g. ops-admin")
            if st.form_submit_button("Transmit Decision", type="primary", use_container_width=True):
                if not reviewer:
                    st.warning("Reviewer ID is required.")
                else:
                    try:
                        post_res = requests.post(
                            f"{BACKEND_URL}/approve",
                            json={"thread_id": st.session_state.thread_id,
                                  "approved": decision == "Approve Merge"},
                        )
                        if post_res.status_code == 200:
                            st.session_state.phase = "resuming"
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Failed: {post_res.text}")
                    except Exception as e:
                        st.error(f"API Error: {e}")

    with col_right:
        # ── Agent reports in RIGHT column with scroll boxes ────────────────
        st.markdown("### Agent Reports")
        for key, title in [
            ("security_report",       "🛡️ Security Agent"),
            ("performance_report",    "⚡ Performance Agent"),
            ("style_report",          "🎨 Style & Quality Agent"),
            ("crag_enhanced_context", "🔍 CRAG Grounding Evaluator"),
            ("final_report_markdown", "📋 Final Aggregated Report"),
        ]:
            if key in values:
                st.markdown(f"**{title}**")
                # Fix applied here: using Streamlit's native container
                with st.container(height=260, border=True):
                    st.markdown(values[key])

    render_chat_widget(
        icon_url=my_local_icon, backend_url=BACKEND_URL,
        btn_bg=btn_bg, shadow_color=shadow_color,
        repo_url=pr_url, github_token=user_token,
    )
    st.stop()

# ── DONE ──────────────────────────────────────────────────────────────────────
elif phase == "done":
    values = st.session_state.graph_state.get("values", {})
    col_left, col_right = st.columns([1, 2])
    with col_left:
        st.markdown("### Pipeline State")
        st.markdown(f"<div class='pipe-step'>1. Fetcher Node {'✅' if 'diff_context' in values else '⏳'}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='pipe-step'>2. Security & Style Agents {'✅' if 'security_report' in values else '⏳'}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='pipe-step'>3. CRAG Evaluator {'✅' if 'crag_enhanced_context' in values else '⏳'}</div>", unsafe_allow_html=True)
        st.markdown("<div class='pipe-step' style='border-color:#10b981;'>4. Completed ✅</div>", unsafe_allow_html=True)
        if values:
            with st.expander("Raw State Dump"):
                st.json(values)
    with col_right:
        st.markdown("### Agent Reports")
        for key, title in [
            ("security_report",       "🛡️ Security Agent"),
            ("performance_report",    "⚡ Performance Agent"),
            ("style_report",          "🎨 Style & Quality Agent"),
            ("crag_enhanced_context", "🔍 CRAG Grounding Evaluator"),
            ("final_report_markdown", "📋 Final Aggregated Report"),
        ]:
            if key in values:
                st.markdown(f"**{title}**")
                # Fix applied here: using Streamlit's native container
                with st.container(height=260, border=True):
                    st.markdown(values[key])

    render_chat_widget(
        icon_url=my_local_icon, backend_url=BACKEND_URL,
        btn_bg=btn_bg, shadow_color=shadow_color,
        repo_url=pr_url, github_token=user_token,
    )
    st.stop()

# ── IDLE ──────────────────────────────────────────────────────────────────────
render_chat_widget(
    icon_url=my_local_icon, backend_url=BACKEND_URL,
    btn_bg=btn_bg, shadow_color=shadow_color,
    repo_url=pr_url, github_token=user_token,
)