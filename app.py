import streamlit as st
import requests
import uuid
import time
import base64
from auth import init_auth_state, check_login_status, is_logged_in, render_landing_page, render_user_header_widget
from chat_with_repo import render_chat_widget
import os
from dotenv import load_dotenv

load_dotenv()


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

    /* ── TOP LOADING BAR ── */
    .prism-topbar {{
        position:fixed; top:0; left:0; right:0; height:3px; z-index:99998;
        background:linear-gradient(90deg,
            transparent 0%, #9d4edd 20%, #fbbf24 50%, #9d4edd 80%, transparent 100%);
        background-size:200% 100%;
        animation:topbarSlide 1.4s ease-in-out infinite;
        box-shadow:0 0 8px #fbbf24, 0 0 2px #9d4edd;
    }}
    @keyframes topbarSlide {{
        0%   {{ background-position:200% 0; }}
        100% {{ background-position:-200% 0; }}
    }}

    /* ── CLOUD POPUP ── */
    .cloud-overlay {{
        position:fixed; inset:0; z-index:999999;
        display:flex; align-items:center; justify-content:center;
        pointer-events:none;
        animation:cloudOverlayFade 10s forwards;
    }}
    @keyframes cloudOverlayFade {{
        0%,80% {{ opacity:1; }} 100% {{ opacity:0; }}
    }}
    .cloud-wrap {{
        position:relative;
        animation:cloudFloat 10s forwards;
    }}
    @keyframes cloudFloat {{
        0%   {{ transform:translateY(60px) scale(0.6); opacity:0; }}
        8%   {{ transform:translateY(-8px) scale(1.04); opacity:1; }}
        14%  {{ transform:translateY(0px) scale(1); opacity:1; }}
        80%  {{ transform:translateY(-4px) scale(1); opacity:1; }}
        100% {{ transform:translateY(-30px) scale(0.9); opacity:0; }}
    }}
    .cloud-body {{
        position:relative;
        background:linear-gradient(135deg,#0a2e1a,#001a0f);
        border:3px solid #00ff99;
        border-radius:50px;
        padding:28px 48px 24px;
        min-width:320px;
        text-align:center;
        box-shadow:
            0 0 0 6px rgba(0,255,153,0.25),
            0 0 40px rgba(0,255,153,0.6),
            0 0 80px rgba(0,255,100,0.25),
            inset 0 1px 0 rgba(255,255,255,0.1);
    }}
    /* Cloud bumps on top */
    .cloud-body::before {{
        content:'';
        position:absolute;
        top:-22px; left:50%; transform:translateX(-50%);
        width:80px; height:44px;
        background:linear-gradient(135deg,#0a2e1a,#001a0f);
        border:2px solid #10b981;
        border-bottom:none;
        border-radius:50px 50px 0 0;
        box-shadow:
            -44px 8px 0 -2px #1a0835,
            -44px 8px 0 0px #10b981,
            44px 8px 0 -2px #1a0835,
            44px 8px 0 0px #10b981;
    }}
    .cloud-checkmark {{
        width:100px; height:100px;
        object-fit:contain;
        background:transparent;
        border-radius:50%;
        filter:drop-shadow(0 0 18px #00ff99) drop-shadow(0 0 8px #00cc77);
        animation:checkPop 0.5s 0.2s cubic-bezier(.34,1.56,.64,1) both, octoBounce 2s 0.7s ease-in-out infinite;
        display:block; margin:0 auto 10px;
        mix-blend-mode:normal;
    }}
    @keyframes checkPop {{
        from {{ transform:scale(0) rotate(-15deg); opacity:0; }}
        to   {{ transform:scale(1) rotate(0deg); opacity:1; }}
    }}
    @keyframes octoBounce {{
        0%,100% {{ transform:translateY(0) rotate(0deg); }}
        30%     {{ transform:translateY(-8px) rotate(-3deg); }}
        60%     {{ transform:translateY(-4px) rotate(2deg); }}
    }}
    .cloud-title {{
        font-family:'Poppins',sans-serif !important;
        font-size:17px; font-weight:700;
        color:#00ff99 !important;
        letter-spacing:0.5px; margin-bottom:4px;
    }}
    .cloud-sub {{
        font-size:12px; color:#6effc0 !important;
        font-family:'Courier New',monospace;
        opacity:0.8;
    }}
    /* sparkles */
    .cloud-sparkle {{
        position:absolute;
        width:6px; height:6px;
        border-radius:50%;
        background:#fbbf24;
        box-shadow:0 0 6px #fbbf24;
        animation:sparklePop 0.6s ease-out forwards;
    }}
    @keyframes sparklePop {{
        0%   {{ transform:scale(0) translate(0,0); opacity:1; }}
        100% {{ transform:scale(1) translate(var(--tx),var(--ty)); opacity:0; }}
    }}
    .repo-row {{
        display:flex; justify-content:space-between; align-items:center;
        padding:8px 12px; border-radius:6px; margin-bottom:6px;
        background:{panel_bg}; border:1px solid {border_color};
        font-family:'Courier New',monospace; font-size:13px;
    }}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# CLOUD POPUP HELPER
# -----------------------------------------------------------------------------
def _cloud_popup_html(title="PR Comment Posted!", sub="Octocat Says Done ✓") -> str:
    # Load octocat from assets folder
    try:
        with open("assets/octocat.png", "rb") as _f:
            _octocat_b64 = base64.b64encode(_f.read()).decode()
        _octocat_uri = f"data:image/png;base64,{_octocat_b64}"
    except FileNotFoundError:
        _octocat_uri = "https://github.githubassets.com/images/modules/logos_page/Octocat.png"
    sparkles = ""
    import math, random
    random.seed(42)
    for i in range(10):
        angle = random.uniform(0, 2 * math.pi)
        dist  = random.uniform(70, 130)
        tx = int(math.cos(angle) * dist)
        ty = int(math.sin(angle) * dist)
        delay = round(random.uniform(0.1, 0.5), 2)
        size  = random.randint(4, 8)
        color = random.choice(["#fbbf24","#34d399","#c084fc","#818cf8"])
        sparkles += (
            f'<div class="cloud-sparkle" style="'
            f'left:calc(50% + {random.randint(-80,80)}px);'
            f'top:calc(50% + {random.randint(-40,40)}px);'
            f'--tx:{tx}px;--ty:{ty}px;'
            f'width:{size}px;height:{size}px;'
            f'background:{color};box-shadow:0 0 6px {color};'
            f'animation-delay:{delay}s;"></div>'
        )
    return f"""
<div class="cloud-overlay">
  <div class="cloud-wrap">
    {sparkles}
    <div class="cloud-body">
      <img class="cloud-checkmark" src="{_octocat_uri}" alt="octocat" />
      <div class="cloud-title">{title}</div>
      <div class="cloud-sub">{sub}</div>
    </div>
  </div>
</div>
"""

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
    labels = ["Fetcher","Security","Style","CRAG","HITL"]
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
  .po-topbar {{
      position:absolute; top:0; left:0; right:0; height:3px;
      background:linear-gradient(90deg,
          transparent 0%, #9d4edd 20%, #fbbf24 50%, #9d4edd 80%, transparent 100%);
      background-size:200% 100%;
      animation:topbarSlide 1.4s ease-in-out infinite;
      box-shadow:0 0 8px #fbbf24, 0 0 2px #9d4edd;
  }}
  @keyframes topbarSlide {{
      0%   {{ background-position:200% 0; }}
      100% {{ background-position:-200% 0; }}
  }}
  .po-ring-wrap {{
      position:relative; width:240px; height:240px;
      display:flex; align-items:center; justify-content:center;
      margin-bottom:28px;
  }}
  .po-ring-wrap canvas.arc-canvas {{
      position:absolute; top:0; left:0; z-index:2;
  }}
  .po-ring-border {{
      position:absolute; inset:0; border-radius:50%; z-index:1;
      background:conic-gradient(
          #fbbf24 0deg, #f59e0b 60deg, #fbbf24 120deg,
          transparent 121deg, transparent 360deg
      );
      -webkit-mask:radial-gradient(farthest-side,transparent calc(100% - 4px),#000 calc(100% - 4px));
      mask:radial-gradient(farthest-side,transparent calc(100% - 4px),#000 calc(100% - 4px));
      animation:rotateBorder 1.2s linear infinite;
  }}
  @keyframes rotateBorder {{ to {{ transform:rotate(360deg); }} }}
  .po-sphere-inner {{
      position:absolute; top:50%; left:50%;
      transform:translate(-50%,-50%);
      width:200px; height:200px; border-radius:50%;
      background:radial-gradient(circle at 35% 32%, #1e0845, #06010f);
      display:flex; flex-direction:column; align-items:center;
      justify-content:center; gap:8px; overflow:hidden; z-index:3;
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
      box-shadow:0 0 8px rgba(251,191,36,0.4);
  }}
</style>

<div class="po-overlay">
  <div class="po-topbar"></div>
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
    g.addColorStop(0, C1); g.addColorStop(1, C2);
    ctx.beginPath();
    ctx.arc(120, 120, 112, angle, angle + span);
    ctx.strokeStyle = g; ctx.lineWidth = 5; ctx.lineCap = 'round'; ctx.stroke();
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

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

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
if "persisted_github_token" not in st.session_state:
    st.session_state.persisted_github_token = ""
with st.sidebar:
    render_user_header_widget({"border_color": border_color, "text_color": text_color})
    st.markdown("---")
    st.markdown("### 🔑 Authentication")
    user_token = st.text_input(
        "GitHub Token (Global)",
        type="password", 
        value=st.session_state.persisted_github_token,
        placeholder="ghp_...",
        help="Required for private repos and setting up webhooks.",
        key="global_token_widget",
    )
    if user_token:
        st.session_state.persisted_github_token = user_token
    user_token = st.session_state.persisted_github_token

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
if "phase"              not in st.session_state: st.session_state.phase              = "idle"
if "thread_id"          not in st.session_state: st.session_state.thread_id          = str(uuid.uuid4())
if "graph_state"        not in st.session_state: st.session_state.graph_state        = {}
if "show_success_popup" not in st.session_state: st.session_state.show_success_popup = False
# Tracks the PR URL for whichever run is currently loaded (manual OR webhook-triggered).
# The old code reused the Tab-1 text input's value everywhere, which broke as soon as
# a webhook-triggered run (with no text input at all) needed to be reviewed/approved.
if "active_pr_url"      not in st.session_state: st.session_state.active_pr_url      = ""
if "active_repo_label"  not in st.session_state: st.session_state.active_repo_label  = ""

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
# 7b. PENDING APPROVALS — auto-refreshes on its own, no manual reload needed
# -----------------------------------------------------------------------------
@st.fragment(run_every=10)
def render_pending_approvals():
    try:
        pending_res = requests.get(f"{BACKEND_URL}/pending-approvals", timeout=5)
        pending = pending_res.json().get("pending", []) if pending_res.status_code == 200 else []
    except Exception:
        pending = []

    if not pending:
        return

    header_col, refresh_col = st.columns([6, 1])
    with header_col:
        st.markdown(f"""
        <div style="background:{panel_bg};border:1px solid #f59e0b;border-radius:8px;
                    padding:10px 14px;margin-bottom:12px;display:flex;justify-content:space-between;align-items:center;">
            <span style="color:#fbbf24;font-weight:600;">⚠️ {len(pending)} run(s) awaiting your review</span>
        </div>
        """, unsafe_allow_html=True)
    with refresh_col:
        if st.button("🔄", key="manual_refresh_pending", help="Check now instead of waiting for the auto-refresh"):
            st.rerun(scope="fragment")

    with st.expander("View pending approvals", expanded=(st.session_state.phase == "idle")):
        for run in pending:
            row_col1, row_col2 = st.columns([5, 1])
            with row_col1:
                badge = "🪝 webhook" if run["trigger_source"] == "webhook" else "✋ manual"
                st.markdown(
                    f"**{run['owner']}/{run['repo']}** PR #{run['pr_number']} · "
                    f"`{badge}` · updated {run['updated_at']}"
                )
            with row_col2:
                if st.button("Review →", key=f"review_{run['thread_id']}", use_container_width=True):
                    # Load THIS run's thread — not whatever's in the manual-review text box.
                    st.session_state.thread_id = run["thread_id"]
                    st.session_state.active_pr_url = run["pr_url"]
                    st.session_state.active_repo_label = f"{run['owner']}/{run['repo']} #{run['pr_number']}"
                    st.session_state.graph_state = {}
                    st.session_state.show_success_popup = False
                    # Route through "polling" so the app fetches fresh state and
                    # naturally lands on the HITL screen once it confirms the run
                    # is actually waiting (rather than assuming it still is).
                    st.session_state.phase = "polling"
                    st.rerun()

render_pending_approvals()

# -----------------------------------------------------------------------------
# 8. INPUT FORM
# -----------------------------------------------------------------------------
tab1, tab2 = st.tabs(["🔍 Single PR Review", "⚡ Automated Webhooks"])

# --- TAB 1: SINGLE PR REVIEW ---
with tab1:
    st.markdown("### Review an Individual Pull Request")
    with st.container(border=True):
        col1, col2 = st.columns([4, 1])
        with col1:
            pr_url = st.text_input(
                "GitHub PR URL",
                value="https://github.com/ABC/PrismAI/pull/1",
                label_visibility="collapsed",
            )
        with col2:
            st.write("") # Alignment spacing
            if st.button("🚀 Run Graph", use_container_width=True, type="primary"):
                st.session_state.thread_id          = str(uuid.uuid4())
                st.session_state.graph_state        = {}
                st.session_state.show_success_popup = False
                st.session_state.active_pr_url      = pr_url
                st.session_state.active_repo_label  = pr_url
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

# --- TAB 2: CONNECT REPO (Webhook & HITL Email) ---
with tab2:
    st.markdown("### 🔗 Connect Repository for Auto-Review")
    st.caption(
        "Once connected, every new or updated PR on this repo automatically runs "
        "through the pipeline — no need to paste links. You'll see it appear under "
        "**pending approvals** above when it reaches the HITL gate."
    )
    with st.container(border=True):
        col_a, col_b = st.columns(2)
        with col_a:
            new_repo = st.text_input("Repository", placeholder="ABC/PrismAI", key="connect_repo_input")
        with col_b:
            notify_email_input = st.text_input(
                "Notify Email (for HITL alerts)",
                placeholder="prismai@example.com",
                key="connect_notify_email",
            )

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("🔌 Connect Repository", use_container_width=True):
            if not user_token:
                st.error("❌ Authentication Missing: Please provide your GitHub Token in the sidebar.")
            else:
                cleaned = new_repo.strip().rstrip("/")
                if cleaned.startswith("https://github.com/"):
                    cleaned = cleaned.replace("https://github.com/", "")

                if "/" in cleaned and notify_email_input:
                    owner_input, repo_input = cleaned.split("/", 1)

                    # ── Resolve canonical casing via GitHub API before storing ──
                    # GitHub's repo lookup is case-insensitive, but the response
                    # always contains the *exact* casing GitHub uses internally —
                    # which is also exactly what webhook payloads will send us
                    # later. If we store whatever casing the user typed, a
                    # mismatch here silently breaks db.get_repo_token() lookups
                    # on every webhook delivery (case-sensitive DB comparisons).
                    gh_resp = None
                    try:
                        gh_resp = requests.get(
                            f"https://api.github.com/repos/{owner_input}/{repo_input}",
                            headers={"Authorization": f"token {user_token}"},
                            timeout=10,
                        )
                    except Exception as e:
                        st.error(f"Couldn't reach GitHub to verify repo: {e}")

                    if gh_resp is None:
                        pass
                    elif gh_resp.status_code != 200:
                        st.error(
                            f"❌ GitHub couldn't find '{owner_input}/{repo_input}' "
                            f"({gh_resp.status_code}). Check the name and your token's access."
                        )
                    else:
                        gh_data = gh_resp.json()
                        owner = gh_data["owner"]["login"]   # canonical casing
                        repo_name = gh_data["name"]         # canonical casing

                        try:
                            resp = requests.post(f"{BACKEND_URL}/repos/connect", json={
                                "owner": owner,
                                "repo": repo_name,
                                "github_token": user_token,
                                "notify_email": notify_email_input,
                            })
                            if resp.status_code == 200:
                                st.success(f"🎉 Successfully connected {owner}/{repo_name}!")
                                st.rerun()
                            else:
                                st.error(f"Server Error ({resp.status_code}): {resp.text}")
                        except Exception as e:
                            st.error(f"Backend Connection Failed: {e}")
                elif not notify_email_input:
                    st.warning("⚠️ Please enter a notification email first.")
                else:
                    st.warning("⚠️ Format must be owner/repo (e.g. YashChauhan/InkNest).")

    # --- Connected repos list, with disconnect ---
    st.markdown("#### Connected Repositories")
    try:
        repos_res = requests.get(f"{BACKEND_URL}/repos", timeout=5)
        connected_repos = repos_res.json().get("repos", []) if repos_res.status_code == 200 else []
    except Exception:
        connected_repos = []

    if not connected_repos:
        st.caption("No repositories connected yet.")
    else:
        for repo_entry in connected_repos:
            r_col1, r_col2 = st.columns([5, 1])
            with r_col1:
                st.markdown(
                    f"<div class='repo-row'>🔗 <b>{repo_entry['owner']}/{repo_entry['repo']}</b>"
                    f"&nbsp;&nbsp;<span style='opacity:0.6;'>connected {repo_entry['connected_at']}</span></div>",
                    unsafe_allow_html=True,
                )
            with r_col2:
                if st.button("Disconnect", key=f"disconnect_{repo_entry['owner']}_{repo_entry['repo']}", use_container_width=True):
                    if not user_token:
                        st.error("❌ GitHub Token required in sidebar to disconnect (removes the webhook on GitHub).")
                    else:
                        try:
                            d_resp = requests.post(f"{BACKEND_URL}/repos/disconnect", json={
                                "owner": repo_entry["owner"],
                                "repo": repo_entry["repo"],
                                "github_token": user_token,
                            })
                            if d_resp.status_code == 200:
                                st.success(f"Disconnected {repo_entry['owner']}/{repo_entry['repo']}")
                                st.rerun()
                            else:
                                st.error(f"Failed to disconnect: {d_resp.text}")
                        except Exception as e:
                            st.error(f"Backend Connection Failed: {e}")

# =============================================================================
# 9. PHASE ROUTER
# =============================================================================
phase = st.session_state.phase
active_pr_url = st.session_state.active_pr_url or pr_url

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
                st.session_state.show_success_popup = True
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

    render_chat_widget(icon_url=my_local_icon, backend_url=BACKEND_URL,
        btn_bg=btn_bg, shadow_color=shadow_color, repo_url=active_pr_url, github_token=user_token)
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
                st.session_state.show_success_popup = True
                st.rerun()
            else:
                time.sleep(2)
                st.rerun()
        else:
            st.error(f"State fetch error: {res.status_code}")
    except Exception as e:
        st.error(f"Resume polling error: {e}")
        st.session_state.phase = "hitl"

    render_chat_widget(icon_url=my_local_icon, backend_url=BACKEND_URL,
        btn_bg=btn_bg, shadow_color=shadow_color, repo_url=active_pr_url, github_token=user_token)
    st.stop()

# ── HITL ──────────────────────────────────────────────────────────────────────
elif phase == "hitl":
    values = st.session_state.graph_state.get("values", {})
    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.markdown("### Pipeline State")
        if st.session_state.active_repo_label:
            st.caption(f"Reviewing: **{st.session_state.active_repo_label}**")
        st.markdown(f"<div class='pipe-step'>1. Fetcher Node {'✅' if 'diff_context' in values else '⏳'}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='pipe-step'>2. Security & Style Agents {'✅' if 'security_report' in values else '⏳'}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='pipe-step'>3. CRAG Evaluator {'✅' if 'crag_enhanced_context' in values else '⏳'}</div>", unsafe_allow_html=True)
        st.markdown("<div class='pipe-step pipe-active' style='border-color:#f59e0b;'>4. HITL Breakpoint (BLOCKED) ⚠️</div>", unsafe_allow_html=True)
        if values:
            with st.expander("Raw State Dump"):
                st.json(values)

        st.markdown("---")
        st.markdown("### 🚨 Decision Center")
        st.error("Pipeline Paused: Awaiting Senior Engineer authorization.")
        with st.form("hitl_form"):
            st.markdown(f"**Thread ID:** `{st.session_state.thread_id}`")
            st.markdown(f"**PR:** {active_pr_url}")
            decision = st.selectbox("Action", ["Approve Merge", "Reject / Drop Request"])
            reviewer = st.text_input("Reviewer ID", placeholder="e.g. ops-admin")
            if st.form_submit_button("Transmit Decision", type="primary", use_container_width=True):
                if not reviewer:
                    st.warning("Reviewer ID is required.")
                else:
                    try:
                        post_res = requests.post(
                            f"{BACKEND_URL}/approve",
                            json={
                                "thread_id": st.session_state.thread_id,
                                "approved": decision == "Approve Merge",
                                "pr_url": active_pr_url,
                                "user_token": user_token,
                            },
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
                with st.container(height=260, border=True):
                    st.markdown(values[key])

    render_chat_widget(icon_url=my_local_icon, backend_url=BACKEND_URL,
        btn_bg=btn_bg, shadow_color=shadow_color, repo_url=active_pr_url, github_token=user_token)
    st.stop()

# ── DONE ──────────────────────────────────────────────────────────────────────
elif phase == "done":
    # Show cute cloud popup once on entry
    if st.session_state.show_success_popup:
        st.markdown(
            _cloud_popup_html(
                title="PR Comment Posted!",
                sub="Successfully pushed to GitHub ✓"
            ),
            unsafe_allow_html=True
        )
        st.session_state.show_success_popup = False   # only show once

    values = st.session_state.graph_state.get("values", {})
    col_left, col_right = st.columns([1, 2])
    with col_left:
        st.markdown("### Pipeline State")
        if st.session_state.active_repo_label:
            st.caption(f"Reviewed: **{st.session_state.active_repo_label}**")
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
                with st.container(height=260, border=True):
                    st.markdown(values[key])

    render_chat_widget(icon_url=my_local_icon, backend_url=BACKEND_URL,
        btn_bg=btn_bg, shadow_color=shadow_color, repo_url=active_pr_url, github_token=user_token)
    st.stop()

# ── IDLE ──────────────────────────────────────────────────────────────────────
render_chat_widget(
    icon_url=my_local_icon, backend_url=BACKEND_URL,
    btn_bg=btn_bg, shadow_color=shadow_color,
    repo_url=pr_url, github_token=user_token,
)
