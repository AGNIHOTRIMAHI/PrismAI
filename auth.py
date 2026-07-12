import streamlit as st
import requests
import base64
import os
import math
import random

from dotenv import load_dotenv

load_dotenv()  # only affects LOCAL runs — Streamlit Cloud ignores this and uses its own Secrets

# IMPORTANT:
# - Locally: your .env's BACKEND_URL=http://localhost:8000 will be picked up by
#   os.getenv() below, since load_dotenv() loads it into the environment first.
# - On Streamlit Cloud: set BACKEND_URL under Settings -> Secrets to your real
#   production Render URL. The fallback below is just a safety net in case that
#   secret is ever missing in production — it should NOT be localhost.
BACKEND_URL = os.getenv("BACKEND_URL", "https://prismai-backend-nih2.onrender.com")

_FALLBACK_PRISM_SVG = """
<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
  <polygon points="100,10 190,70 155,190 45,190 10,70" fill="none" stroke="#92BEE1" stroke-width="3"/>
  <polygon points="100,10 190,70 100,110" fill="#92BEE1" opacity="0.55"/>
  <polygon points="190,70 155,190 100,110" fill="#C5B1F8" opacity="0.55"/>
  <polygon points="155,190 45,190 100,110" fill="#041235" opacity="0.75"/>
  <polygon points="45,190 10,70 100,110" fill="#C5B1F8" opacity="0.45"/>
  <polygon points="10,70 100,10 100,110" fill="#92BEE1" opacity="0.65"/>
</svg>
"""


def init_auth_state():
    if "auth_checked" not in st.session_state:
        st.session_state.auth_checked = False
    if "github_user" not in st.session_state:
        st.session_state.github_user = None
    if "prismai_session_id" not in st.session_state:
        st.session_state.prismai_session_id = None

    if "session_id" in st.query_params:
        st.session_state.prismai_session_id = st.query_params["session_id"]
        del st.query_params["session_id"]


def check_login_status():
    session_id = st.session_state.get("prismai_session_id")
    if not session_id:
        st.session_state.github_user = None
        return False
    try:
        resp = requests.get(
            f"{BACKEND_URL}/auth/me",
            cookies={"prismai_session": session_id},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("logged_in"):
                st.session_state.github_user = data.get("user")
                return True
    except requests.RequestException:
        pass
    st.session_state.github_user = None
    return False


def is_logged_in() -> bool:
    return st.session_state.get("github_user") is not None


def get_image_base64(filepath):
    try:
        with open(filepath, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return ""


def _generate_node_network(num_nodes: int = 70, seed: int = 7,
                            width: int = 800, height: int = 1000,
                            right_bias: float = 1.0):
    rng = random.Random(seed)

    nodes = []
    for i in range(num_nodes):
        x = int((rng.random() ** right_bias) * (width - 10)) + 5
        y = rng.randint(20, height - 20)
        is_primary = (i % 3 == 0)
        r = rng.choice([7, 8, 10, 12]) if is_primary else rng.choice([4, 5, 6])
        nodes.append({"x": x, "y": y, "r": r, "primary": is_primary})

    edge_set = set()
    for i, n in enumerate(nodes):
        dists = sorted(
            (
                (math.hypot(n["x"] - m["x"], n["y"] - m["y"]), j)
                for j, m in enumerate(nodes) if j != i
            ),
            key=lambda t: t[0],
        )
        neighbor_count = 3 if n["primary"] else 2
        for _, j in dists[:neighbor_count]:
            edge_set.add(tuple(sorted((i, j))))

    for _ in range(num_nodes):
        i, j = rng.randrange(num_nodes), rng.randrange(num_nodes)
        if i != j:
            edge_set.add(tuple(sorted((i, j))))

    node_svg_parts = []
    for n in nodes:
        cls = "primary-node" if n["primary"] else "distant-node"
        node_svg_parts.append(
            f'<circle class="{cls}" cx="{n["x"]}" cy="{n["y"]}" r="{n["r"]}" />'
        )

    edge_svg_parts = []
    for idx, (i, j) in enumerate(sorted(edge_set)):
        a, b = nodes[i], nodes[j]
        dense_cls = "dense-link" if idx % 3 == 0 else ""
        edge_svg_parts.append(
            f'<line class="{dense_cls}" x1="{a["x"]}" y1="{a["y"]}" '
            f'x2="{b["x"]}" y2="{b["y"]}" />'
        )

    return "".join(node_svg_parts), "".join(edge_svg_parts)


def render_animated_background(theme: dict = None, right_bias: float = 1.0,
                                fade_side: str = "none"):
    theme = theme or {}
    btn_bg = theme.get("btn_bg", "#92BEE1")
    btn_hover = theme.get("btn_hover", "#C5B1F8")
    lavender = theme.get("lavender", "#C5B1F8")

    node_svg, edge_svg = _generate_node_network(right_bias=right_bias)

    if fade_side == "right":
        mask_css = """
    -webkit-mask-image: linear-gradient(90deg, transparent 0%, rgba(0,0,0,0.35) 35%, #000 70%);
    mask-image: linear-gradient(90deg, transparent 0%, rgba(0,0,0,0.35) 35%, #000 70%);
"""
    elif fade_side == "left":
        mask_css = """
    -webkit-mask-image: linear-gradient(90deg, #000 30%, rgba(0,0,0,0.35) 65%, transparent 100%);
    mask-image: linear-gradient(90deg, #000 30%, rgba(0,0,0,0.35) 65%, transparent 100%);
"""
    else:
        mask_css = ""

    st.markdown(f"""
<style>
html, body, [data-testid="stAppViewContainer"], .main, .block-container {{
    overflow-y: visible !important;
    overflow-x: hidden !important;
    height: auto !important;
    min-height: 100vh !important;
}}
[data-testid="stAppViewContainer"] {{ overflow-y: auto !important; }}
.stApp {{ background-color: transparent; }}
.block-container {{ position: relative !important; z-index: 1 !important; }}

.aurora-bg {{
    position: fixed; inset: 0; z-index: 0; overflow: hidden; pointer-events: none;
    background-color: #050b1f;
    background-image: repeating-linear-gradient(
        180deg,
        rgba(146, 190, 225, 0.05) 0px,
        rgba(146, 190, 225, 0.05) 90px,
        rgba(197, 177, 248, 0.045) 90px,
        rgba(197, 177, 248, 0.045) 180px
    );
}}
.aurora-blob {{ position: absolute; border-radius: 50%; filter: blur(90px); }}
.aurora-blob.b1 {{
    width: 620px; height: 620px; top: -12%; right: -8%;
    background: radial-gradient(circle, {btn_hover} 0%, transparent 68%);
    opacity: 0.55; animation: driftA 24s ease-in-out infinite;
}}
.aurora-blob.b2 {{
    width: 520px; height: 520px; bottom: -16%; left: -10%;
    background: radial-gradient(circle, {btn_bg} 0%, transparent 68%);
    opacity: 0.45; animation: driftB 28s ease-in-out infinite;
}}
.aurora-blob.b3 {{
    width: 460px; height: 460px; top: 38%; left: 58%;
    background: radial-gradient(circle, {lavender} 0%, transparent 70%);
    opacity: 0.4; animation: driftC 32s ease-in-out infinite;
}}
.aurora-blob.b4 {{
    width: 380px; height: 380px; top: 4%; left: 28%;
    background: radial-gradient(circle, {btn_bg} 0%, transparent 70%);
    opacity: 0.28; animation: driftA 20s ease-in-out infinite reverse;
}}
@keyframes driftA {{ 0%,100% {{ transform: translate(0,0) scale(1); }} 50% {{ transform: translate(-50px,60px) scale(1.12); }} }}
@keyframes driftB {{ 0%,100% {{ transform: translate(0,0) scale(1); }} 50% {{ transform: translate(60px,-40px) scale(1.15); }} }}
@keyframes driftC {{ 0%,100% {{ transform: translate(0,0) scale(1); }} 50% {{ transform: translate(-40px,-50px) scale(1.1); }} }}

.aurora-sparkles {{
    position: absolute; inset: 0;
    background-image: radial-gradient(circle, rgba(255,255,255,0.5) 1px, transparent 1.4px);
    background-size: 90px 90px;
    opacity: 0.25;
}}
.aurora-vignette {{
    position: absolute; inset: 0;
    background:
        radial-gradient(ellipse at 50% 50%, transparent 35%, #050b1f 92%),
        linear-gradient(180deg, #050b1f 0%, transparent 10%, transparent 90%, #050b1f 100%);
}}

@media (max-width: 768px) {{
    .aurora-blob.b1 {{ width: 380px; height: 380px; }}
    .aurora-blob.b2 {{ width: 340px; height: 340px; }}
    .aurora-blob.b3 {{ width: 300px; height: 300px; }}
    .aurora-blob.b4 {{ width: 260px; height: 260px; }}
}}

.node-network-container {{
    position: fixed;
    inset: -10%;
    width: 120vw;
    height: 120vh;
    z-index: 0;
    transform: scale(1.15);
    pointer-events: none;
    opacity: 0.5;
    animation: driftNetwork 30s ease-in-out infinite alternate;
{mask_css}}}
@keyframes driftNetwork {{
    0% {{ transform: translate(0px, 0px) scale(1); }}
    50% {{ transform: translate(-20px, -15px) scale(1.02); }}
    100% {{ transform: translate(15px, 20px) scale(1.03); }}
}}

.network-nodes .primary-node {{
    fill: #92BEE1;
    filter: drop-shadow(0 0 8px rgba(146, 190, 225, 0.9));
    animation: pulseNode 4s infinite alternate;
}}
.network-nodes .distant-node {{
    fill: #C5B1F8;
    opacity: 0.45;
    filter: drop-shadow(0 0 3px rgba(197, 177, 248, 0.5));
    animation: pulseNode 6s infinite alternate reverse;
}}
.network-edges line {{
    stroke: rgba(197, 177, 248, 0.25);
    stroke-width: 1;
    animation: pulseEdge 3.5s infinite alternate;
}}
.network-edges line.dense-link {{
    stroke: rgba(146, 190, 225, 0.2);
    stroke-width: 0.75;
    stroke-dasharray: 3 3;
}}
.network-nodes circle:nth-child(odd) {{ animation-delay: 0.8s; }}
.network-nodes circle:nth-child(3n) {{ animation-delay: 2.2s; }}
.network-edges line:nth-child(even) {{ animation-delay: 1.2s; }}

@keyframes pulseNode {{
    0% {{ opacity: 0.3; transform: scale(0.85); transform-origin: center; }}
    100% {{ opacity: 1; transform: scale(1.25); transform-origin: center; }}
}}
@keyframes pulseEdge {{
    0% {{ opacity: 0.15; }}
    100% {{ opacity: 0.65; }}
}}
</style>

<div class="aurora-bg">
    <div class="aurora-blob b1"></div>
    <div class="aurora-blob b2"></div>
    <div class="aurora-blob b3"></div>
    <div class="aurora-blob b4"></div>
    <div class="aurora-sparkles"></div>
    <div class="aurora-vignette"></div>
    <div class="node-network-container">
        <svg viewBox="0 0 800 1000" xmlns="http://www.w3.org/2000/svg" style="width: 100%; height: 100%;">
            <g class="network-edges">{edge_svg}</g>
            <g class="network-nodes">{node_svg}</g>
        </svg>
    </div>
</div>
    """, unsafe_allow_html=True)


def render_landing_page(theme: dict):
    theme = theme or {}
    bg_color = theme.get("bg_color", "#041235")
    text_color = theme.get("text_color", "#dbe4fb")
    panel_bg = theme.get("panel_bg", "rgba(146, 190, 225, 0.10)")
    border_color = theme.get("border_color", "rgba(255, 255, 255, 0.16)")
    shadow_color = theme.get("shadow_color", "rgba(146, 190, 225, 0.30)")
    title_color = theme.get("title_color", "#ffffff")
    btn_bg = theme.get("btn_bg", "#92BEE1")
    btn_hover = theme.get("btn_hover", "#C5B1F8")
    lavender = theme.get("lavender", "#C5B1F8")

    MASCOT_ASSET_PATH = "assets/mascot.png"
    encoded_mascot = get_image_base64(MASCOT_ASSET_PATH)
    mascot_src = f"data:image/png;base64,{encoded_mascot}" if encoded_mascot else ""

    PRISM_ASSET_PATH = "assets/image.png"
    encoded_prism = get_image_base64(PRISM_ASSET_PATH)
    prism_src = f"data:image/png;base64,{encoded_prism}" if encoded_prism else ""

    render_animated_background(theme, right_bias=0.55, fade_side="right")

    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Kavoon&family=Satisfy&family=Space+Grotesk:wght@300;400;500;600&family=Roboto+Mono:wght@400;700&display=swap');

div[data-testid="stVerticalBlock"] > div[data-testid="element-container"] {{ margin-bottom: 0 !important; }}
div[data-testid="stLinkButton"] {{ margin: 4px 0 !important; }}
.block-container {{
    padding-top: 2rem !important;
    padding-bottom: 0rem !important;
    max-width: 95% !important;
}}
.brand-title {{
    display: flex; align-items: center; gap: 10px;
    margin: 0 0 22px 4px;
}}
.brand-title .mark {{
    width: 26px; height: 26px;
    background: conic-gradient(from 45deg, {btn_bg}, {lavender}, {btn_bg});
    clip-path: polygon(50% 0%, 100% 38%, 82% 100%, 18% 100%, 0% 38%);
}}
.brand-title span {{
    font-family: 'Kavoon', cursive !important;
    font-size: 1.4rem;
    color: {title_color};
    letter-spacing: 0.5px;
}}
.brand-title span b {{
    background: linear-gradient(100deg, {btn_bg}, {lavender});
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    font-weight: 400;
}}

.hero-glass-card,.content-glass {{
    background: {panel_bg};
    border: 1px solid {border_color};
    border-radius: 24px;
    padding: 32px 28px;
    width: 100%;
    box-sizing: border-box;
    backdrop-filter: blur(22px) saturate(160%);
    -webkit-backdrop-filter: blur(22px) saturate(160%);
    box-shadow: 0 8px 40px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.07);
}}
.hero-glass-card {{ padding: 36px 28px; }}
.hero-glass-card, 
.stat-card, 
.feat-card, 
.agent-card, 
.chat-glass-panel, 
.cta-banner {{
    background: rgba(4, 18, 53, 0.25) !important; 
    backdrop-filter: blur(24px) saturate(160%) !important;
    -webkit-backdrop-filter: blur(24px) saturate(160%) !important;
    border: 1px solid rgba(146, 190, 225, 0.15) !important;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
    border-radius: 16px;
    position: relative;
    overflow: hidden;
}}

.hero-glass-card::after, 
.stat-card::after, 
.feat-card::after, 
.agent-card::after, 
.chat-glass-panel::after, 
.cta-banner::after {{
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    z-index: 0;
    background-image: repeating-linear-gradient(
        -45deg,
        transparent,
        transparent 2px,
        rgba(255, 255, 255, 0.03) 2px,
        rgba(255, 255, 255, 0.03) 4px
    );
}}

.hero-glass-card > *, 
.stat-card > *, 
.feat-card > *, 
.agent-card > *, 
.chat-glass-panel > *, 
.cta-banner > * {{
    position: relative;
    z-index: 1;
}}

.feat-card {{
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}}

.feat-card:hover {{
    border-color: rgba(146, 190, 225, 0.5) !important;
    box-shadow: 0 8px 40px rgba(146, 190, 225, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.2) !important;
    transform: translateY(-4px);
    background: rgba(4, 18, 53, 0.4) !important; 
}}
.split-left {{
    display: flex; flex-direction: column; justify-content: center;
    padding: 40px 40px 10px 10px; height: auto;
}}

.cursive-subheading {{
    font-family: 'Satisfy', cursive !important; font-size: 2.3rem !important;
    background: linear-gradient(90deg, #ffffff 0%, {lavender} 25%, #ffffff 50%, {btn_bg} 75%, #ffffff 100%);
    background-size: 200% auto; -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin: 0px 0 15px 0 !important; font-weight: 600; letter-spacing: 0.6px;
    text-shadow: 0 0 8px {shadow_color};
    animation: textShimmer 4s linear infinite;
}}

.landing-title {{
    font-family: 'Kavoon', cursive !important; font-size: clamp(2rem, 5vw, 3.8rem) !important;
    background: linear-gradient(100deg, {title_color} 0%, {btn_bg} 45%, {lavender} 80%, {title_color} 100%);
    background-size: 220% auto;
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin: 0 0 5px 0!important; line-height: 1.1; letter-spacing: 1px;
    animation: textShimmer 7s ease-in-out infinite;
}}
.landing-punch {{
    font-family: 'Space Grotesk', sans-serif !important; font-weight: 500 !important;
    font-size: 1.05rem !important; color: {lavender} !important;
    letter-spacing: 0.3px; margin: 6px 0 18px 0 !important;
}}
.landing-subtext {{
    font-family: 'Space Grotesk', sans-serif !important; color: #cbd5e1 !important;
    font-size: 1.4rem; max-width: 460px; margin: 0 0 35px 0!important;
    line-height: 1.5; font-weight: 300;
}}

.terminal-container {{
    max-width: 460px; width: 100%; margin-top: 35px; background: rgba(4, 18, 53, 0.55);
    border-radius: 10px; border: 1px solid {border_color}; overflow: hidden;
    backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
    box-shadow: 0 8px 30px rgba(0,0,0,0.35);
}}
.terminal-header {{
    display: flex; align-items: center; padding: 10px 14px;
    background: rgba(146, 190, 225, 0.08); border-bottom: 1px solid {border_color};
}}
.mac-dots {{ display: flex; gap: 6px; margin-right: 15px; }}
.dot {{ width: 10px; height: 10px; border-radius: 50%; }}
.dot.red {{ background: #ff5f56; }} .dot.yellow {{ background: #ffbd2e; }} .dot.green {{ background: #27c93f; }}
.terminal-title {{ font-family: 'Roboto Mono', monospace; font-size: 11px; color: #8b949e; }}
.terminal-body {{
    padding: 18px; font-family: 'Roboto Mono', monospace; font-size: 13px;
    color: #e2e8f0; line-height: 1.6; word-break: break-word;
}}

@keyframes blink {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0; }} }}
@keyframes textShimmer {{ 0% {{ background-position: 0% center; }} 50% {{ background-position: 100% center; }} 100% {{ background-position: 0% center; }} }}
.blinking-cursor {{
    display: inline-block; width: 4px; height: 16px; background-color: {lavender} !important;
    vertical-align: middle; box-shadow: 0 0 8px {shadow_color};
    animation: blink 1s step-end infinite; margin-left: 4px;
}}

/* ---------- HERO VISUAL — reduced height + tighter bottom margin so the
   gap before the "live demo" radar section below is much smaller ---------- */
.hero-visual {{
    position: relative; height: 420px; display: flex; align-items: center; justify-content: center;
    overflow: visible;
}}
.hero-glow {{
    position: absolute; width: 480px; height: 480px; border-radius: 50%; z-index: 0;
    background: radial-gradient(circle at center, {btn_hover}40 0%, {btn_bg}22 40%, transparent 72%);
    filter: blur(42px);
}}
.hero-node-network {{
    position: absolute; inset: 0; z-index: 1;
    pointer-events: none;
}}
.mascot-float {{
    width: 420px; max-width: 80%; position: relative; z-index: 2;
    animation: mascotFloat 4.5s ease-in-out infinite;
    filter: drop-shadow(0 24px 45px rgba(0,0,0,0.6));
}}
@keyframes mascotFloat {{ 0%,100%{{transform:translateY(0px);}} 50%{{transform:translateY(-18px);}} }}

.inline-prism-container {{
    display: flex; justify-content: center; align-items: center;
    width: 100%; margin: 60px 0 20px 0;
}}
.inline-prism {{
    width: 110px; height: 110px;
    animation: inlinePrismSpin 10s linear infinite;
    filter: drop-shadow(0 0 18px {shadow_color});
}}
@keyframes inlinePrismSpin {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}

.pai-section {{ padding: 60px 0; position: relative; }}
.pai-tag {{
    font-family: 'Roboto Mono', monospace; font-size: 0.75rem; color: {btn_bg};
    letter-spacing: 2px; text-transform: uppercase; margin-bottom: 8px;
}}
.pai-h2 {{
    font-family: 'Kavoon', cursive !important; font-size: 2.1rem !important; color: {title_color} !important;
    margin: 0 0 12px 0 !important; line-height: 1.25;
}}
.pai-lead {{ color: #b9c6ea !important; font-weight: 300; line-height: 1.6; max-width: 640px; }}

.stat-card, .feat-card, .agent-card {{
    background: {panel_bg};
    border: 1px solid {border_color};
    backdrop-filter: blur(18px) saturate(140%);
    -webkit-backdrop-filter: blur(18px) saturate(140%);
    box-shadow: 0 4px 24px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.04);
    box-sizing: border-box;
}}

.stat-card {{
    border-radius: 16px;
    padding: 22px 14px; text-align: center; height: 100%; min-height: 118px;
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    margin-bottom: 20px;
}}
.stat-card .num {{
    font-family: 'Kavoon', cursive; font-size: 2rem; color: {title_color};
    white-space: nowrap; line-height: 1.1;
}}
.stat-card .lbl {{
    font-family: 'Roboto Mono', monospace; font-size: 0.7rem; color: {lavender};
    text-transform: uppercase; letter-spacing: 0.5px; margin-top: 6px;
}}

.feat-card {{
    border-radius: 16px;
    padding: 24px; height: 100%; min-height: 170px; margin-bottom: 28px;
    transition: all 0.2s ease;
}}
.feat-card:hover {{ border-color: {btn_bg}; box-shadow: 0 0 24px {shadow_color}; transform: translateY(-3px); }}
.feat-card .icon {{ font-size: 1.7rem; display: block; margin-bottom: 10px; }}
.feat-card h4 {{ margin: 0 0 6px 0 !important; color: {title_color} !important; font-size: 1rem !important; }}
.feat-card p {{ margin: 0 !important; color: #b9c6ea !important; font-size: 0.85rem !important; font-weight: 300; line-height: 1.5; }}

.agent-card {{
    border-radius: 16px;
    padding: 20px 10px; text-align: center; height: 100%; margin-bottom: 20px;
}}
.agent-avatar {{
    width: 54px; height: 54px; border-radius: 50%; margin: 0 auto 10px auto;
    display: flex; align-items: center; justify-content: center; font-size: 1.4rem;
    background: radial-gradient(circle at 35% 30%, {btn_bg}44, {bg_color}); border: 1px solid {btn_bg};
}}
.agent-card h5 {{ margin: 0 0 2px 0 !important; color: {title_color} !important; font-size: 0.9rem !important; }}
.agent-card span {{ font-family: 'Roboto Mono', monospace; font-size: 0.65rem; color: {lavender}; }}

.step-row {{ display: flex; gap: 16px; margin-bottom: 26px; }}
.step-num {{
    flex-shrink: 0; width: 36px; height: 36px; border-radius: 50%; background: {panel_bg};
    border: 1px solid {btn_bg}; color: {btn_bg}; display: flex; align-items: center; justify-content: center;
    font-family: 'Roboto Mono', monospace; font-weight: 700;
    backdrop-filter: blur(10px);
}}
.step-row h4 {{ margin: 2px 0 4px 0 !important; color: {title_color} !important; font-size: 1.02rem !important; }}
.step-row p {{ margin: 0 !important; color: #b9c6ea !important; font-size: 0.88rem !important; font-weight: 300; }}

.chat-glass-panel {{
    background: {panel_bg}; border: 1px solid {border_color}; border-radius: 20px;
    padding: 22px; backdrop-filter: blur(20px) saturate(140%); -webkit-backdrop-filter: blur(20px) saturate(140%);
    box-shadow: 0 8px 32px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.04);
    max-width: 480px; width: 100%; box-sizing: border-box;
}}
.chat-bubble {{
    border-radius: 14px; padding: 12px 16px; margin-bottom: 12px; font-family: 'Space Grotesk', sans-serif;
    font-size: 0.9rem; line-height: 1.5; max-width: 88%; box-sizing: border-box;
    backdrop-filter: blur(14px) saturate(160%);
    -webkit-backdrop-filter: blur(14px) saturate(160%);
    box-shadow: 0 4px 18px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.08);
}}
.chat-bubble.user {{
    background: linear-gradient(135deg, {btn_bg}30, {btn_bg}0d);
    border: 1px solid {btn_bg}55; color: #eef2ff;
    margin-left: auto; border-bottom-right-radius: 4px;
}}
.chat-bubble.agent {{
    background: linear-gradient(135deg, {lavender}28, {lavender}0a);
    border: 1px solid {lavender}44; color: #eef2ff;
    margin-right: auto; border-bottom-left-radius: 4px;
}}
.chat-source-pill {{
    display: inline-block; font-family: 'Roboto Mono', monospace; font-size: 0.65rem;
    color: {lavender}; border: 1px solid {lavender}55; border-radius: 999px;
    padding: 2px 8px; margin-top: 8px; margin-right: 6px;
}}

.cta-banner {{
    background: {panel_bg}; border: 1px solid {btn_bg};
    border-radius: 24px; padding: 50px 40px; text-align: center; box-shadow: 0 0 40px {shadow_color};
    backdrop-filter: blur(20px) saturate(140%); -webkit-backdrop-filter: blur(20px) saturate(140%);
}}
.cta-banner h3 {{ font-family: 'Kavoon', cursive; font-size: 1.8rem; color: {title_color}; margin: 0 0 10px 0; }}
.cta-banner p {{ color: #cbd5e1; font-weight: 300; margin: 0 0 4px 0; }}

.pai-footer {{
    padding: 30px 0 50px 0; text-align: center; color: #7f8fc2; font-size: 0.8rem;
    font-family: 'Roboto Mono', monospace; border-top: 1px solid {border_color}; margin-top: 20px;
}}

/* ---------- "See It In Action" ghost button — now has a real hover state.
   Inline style="" attributes can't hold :hover, so the effect is defined
   here as a class rule and applied to the anchor below. ---------- */
.see-action-btn {{
    display:inline-flex; align-items:center; justify-content:center; gap:10px;
    background: transparent; color: {btn_bg} !important;
    font-weight: 700; font-size: 1.25rem;
    padding: 16px 30px; border-radius: 12px;
    border: 2px solid {btn_bg}; text-decoration: none;
    transition: all 0.25s ease; width: 100%; box-sizing: border-box;
    scroll-behavior: smooth;
}}
.see-action-btn:hover {{
    background: {btn_bg} !important;
    color: #041235 !important;
    transform: translateY(-4px) scale(1.02);
    box-shadow: 0 12px 25px {shadow_color};
}}
.see-action-btn:active {{
    transform: translateY(2px) scale(0.98);
    box-shadow: 0 4px 10px {shadow_color};
}}
html {{ scroll-behavior: smooth; }}

@media (max-width: 768px) {{
    .split-left {{ padding: 20px 6px 10px 6px; }}
    .landing-title {{ font-size: 2.4rem !important; }}
    .cursive-subheading {{ font-size: 1.6rem !important; }}
    .landing-subtext {{ font-size: 1.05rem; max-width: 100%; }}
    .hero-visual {{ height: 300px; margin-top: 10px; margin-bottom: -20px; }}
    .hero-glow {{ width: 300px; height: 300px; filter: blur(30px); }}
    .mascot-float {{ width: 260px; }}
    .terminal-container {{ max-width: 100%; }}
    .pai-h2 {{ font-size: 1.5rem !important; }}
    .stat-card {{ min-height: 96px; padding: 16px 10px; }}
    .stat-card .num {{ font-size: 1.4rem; }}
    .feat-card {{ min-height: auto; padding: 18px; }}
    .chat-glass-panel {{ padding: 16px; }}
    .cta-banner {{ padding: 34px 20px; }}
    .hero-glass-card {{ padding: 26px 20px; border-radius: 18px; }}
}}
</style>
    """, unsafe_allow_html=True)

    left_col, right_col = st.columns([1, 1.3], gap="large")

    with left_col:

        st.markdown(f"""
        <div class="split-left">
            <div class="brand-title">
                  <span>🟦 Prism<b>AI</b></span>
            </div>
                <h1 class="landing-title">Ship code your<br>reviewers trust</h1>
                <div class="cursive-subheading">Refract &middot; Analyze &middot; Approve</div>
                <div class="landing-punch">Autonomous review agents. One human final call.</div>
                <p class="landing-subtext" style="margin-bottom:0 !important;">
                    PrismAI runs every pull request through security and style
                    review agents &mdash; then hands the final call to you before anything merges.
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <style>
        div[data-testid="stLinkButton"] a {{
            background: {btn_bg} !important; color: #041235 !important;
            font-weight: 600 !important; font-size: 1.5rem !important;
            padding: 16px 36px !important; border-radius: 12px !important;
            text-decoration: none !important; box-shadow: 0 4px 15px {shadow_color} !important;
            border: none !important; display: inline-flex !important;
            align-items: center !important; gap: 12px !important; transition: all 0.25s ease;
        }}
        div[data-testid="stLinkButton"] a p {{
            font-weight: 700 !important; font-size: 1.25rem !important;
            margin: 0 !important; display: flex !important; align-items: center !important; gap: 12px !important;
        }}
        div[data-testid="stLinkButton"] a:hover {{
            filter: brightness(1.08) !important; transform: translateY(-4px) scale(1.02) !important;
            box-shadow: 0 12px 25px {shadow_color} !important;
        }}
        div[data-testid="stLinkButton"] a:active {{
            transform: translateY(2px) scale(0.98) !important; box-shadow: 0 4px 10px {shadow_color} !important;
            filter: brightness(1.0) !important; transition: all 0.1s ease-out !important;
        }}
        div[data-testid="stLinkButton"] a p::before {{
            content: ""; display: inline-block; width: 26px; height: 26px; margin-right: 4px;
            vertical-align: middle; background-color: #041235;
            -webkit-mask-repeat: no-repeat; mask-repeat: no-repeat;
            -webkit-mask-size: contain; mask-size: contain;
            -webkit-mask-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path d='M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z'/></svg>");
            mask-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path d='M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z'/></svg>");
        }}
        </style>
        """, unsafe_allow_html=True)
        # NOTE: previously there was a `[data-testid="stHorizontalBlock"] { gap: 0.2rem !important; }`
        # rule here. It had no scoping, so it squashed the gap on every st.columns()
        # row on the whole page — including the feature grid, stat bar, and
        # capabilities grid further down — which is why those boxes looked like
        # they had almost no space between them. Removed; the default "small"
        # column gap below is enough for these two buttons.
        st.markdown("""
        <style>
        .st-key-hero_btn_row [data-testid="stHorizontalBlock"] { gap: 0.3rem !important; }
        </style>
        """, unsafe_allow_html=True)
        with st.container(key="hero_btn_row"):
            btn_col1, btn_col2 = st.columns([1, 1], gap="small")
            with btn_col1:
                  st.link_button("Sign in with GitHub", f"{BACKEND_URL}/auth/github/login")
            with btn_col2:
               st.markdown(f"""
               <a href="#live-demo" class="see-action-btn">
                        See It In Action ➜
                </a>
              """, unsafe_allow_html=True)
        st.markdown(f"""
         <div class="split-left" style="height:auto; padding-top:20px;">
            <div class="terminal-container">
                <div class="terminal-header">
                    <div class="mac-dots">
                        <div class="dot red"></div><div class="dot yellow"></div><div class="dot green"></div>
                    </div>
                    <div class="terminal-title">bash</div>
                </div>
                <div class="terminal-body">
                    <span style="color:#6b7280;"># Connect your repo. Let agents take it from here.</span><br><br>
                    <span style="color:{btn_bg}; font-weight: bold;">$</span> github auth --scope repo,read:user<span class="blinking-cursor"></span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with right_col:

        img_tag = f'<img class="mascot-float" src="{mascot_src}" alt="PrismAI mascot" />' if mascot_src else '<div style="font-size:8rem;">🟪</div>'
        hero_node_svg, hero_edge_svg = _generate_node_network(num_nodes=26, width=480, height=560)

        st.markdown(f"""
        <div class="hero-visual">
            <div class="hero-glow"></div>
            <div class="hero-node-network">
                <svg viewBox="0 0 480 560" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;">
                    <g class="network-edges">{hero_edge_svg}</g>
                    <g class="network-nodes">{hero_node_svg}</g>
                </svg>
            </div>
            {img_tag}
        </div>
        """, unsafe_allow_html=True)

    # =========================================================================
    # LIVE COMMAND CENTER
    # FIX: the previous version had a blank line between the opening <div
    # id="live-demo"> tag and the <h2> inside it. CommonMark treats a blank
    # line as the end of a raw-HTML block, so everything after it (the <h2>
    # and its own closing </div>) got parsed as plain Markdown text instead of
    # rendered HTML — which is exactly the literal "<h2 class=...>" text
    # showing up on the page. Removing the blank line fixes it.
    # =========================================================================
    st.markdown("""
    <div id="live-demo" style="margin-top:10px; margin-bottom:16px;">
        <h2 class="pai-h2" style="margin-bottom:0 !important;">Navigate through the world of PrismAI</h2>
    </div>
    """, unsafe_allow_html=True)

    SECURITY_MASCOT_PATH = "assets/mascot1.png"
    encoded_security_mascot = get_image_base64(SECURITY_MASCOT_PATH)
    security_icon_html = (
        f'<img src="data:image/png;base64,{encoded_security_mascot}" alt="Security agent" style="width:100%;height:100%;object-fit:cover;border-radius:50%;" />'
        if encoded_security_mascot else "🛡️"
    )

    st.markdown("""
    <style>
    .radar-container {
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        background: rgba(4, 18, 53, 0.25); border: 1px solid rgba(146, 190, 225, 0.15);
        border-radius: 24px; backdrop-filter: blur(24px) saturate(160%);
        -webkit-backdrop-filter: blur(24px) saturate(160%);
        box-shadow: 0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.08);
        padding: 40px 20px; max-width: 450px; margin: 0 auto;
    }
    .cc-radar {
        width: 220px; height: 220px; border-radius: 50%; position: relative;
        border: 1px solid rgba(146,190,225,0.22);
        background: radial-gradient(circle, rgba(146,190,225,0.06), transparent 72%);
    }
    .cc-radar-ring { position: absolute; inset: 24px; border-radius: 50%; border: 1px solid rgba(197,177,248,0.15); }
    .cc-radar-sweep {
        position: absolute; inset: 0; border-radius: 50%; overflow: hidden;
        animation: ccSpin 4s linear infinite;
    }
    .cc-radar-sweep::before {
        content: ""; position: absolute; inset: 0;
        background: conic-gradient(from 0deg, transparent 0deg, rgba(146,190,225,0.4) 22deg, transparent 55deg);
    }
    @keyframes ccSpin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    .cc-radar-center {
        position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%); text-align: center;
        font-family: 'Roboto Mono', monospace; color: #c5b1f8;
    }
    .cc-radar-center .pr-id { font-size: 0.7rem; opacity: 0.8; }
    .cc-radar-center .pr-status { font-size: 0.8rem; color: #ffffff; margin-top: 2px; animation: ccTextPulse 1.8s ease-in-out infinite; }
    @keyframes ccTextPulse { 0%,100% { opacity: 0.6; } 50% { opacity: 1; } }
    .cc-agent-node {
        position: absolute; width: 50px; height: 50px; border-radius: 50%;
        background: #0c1222; border: 1.5px solid #2e4a8b;
        display: flex; align-items: center; justify-content: center; font-size: 1.3rem;
        overflow: hidden; animation: ccNodePulse 4s ease-in-out infinite;
    }
    .cc-agent-node.top { top: -12px; left: 50%; transform: translateX(-50%); animation-delay: 0s; }
    .cc-agent-node.right { right: -12px; top: 50%; transform: translateY(-50%); animation-delay: 1s; }
    .cc-agent-node.bottom { bottom: -12px; left: 50%; transform: translateX(-50%); animation-delay: 2s; }
    .cc-agent-node.left { left: -12px; top: 50%; transform: translateY(-50%); animation-delay: 3s; }
    @keyframes ccNodePulse {
        0%, 92%, 100% { box-shadow: 0 0 0 rgba(197,177,248,0); border-color: #2e4a8b; }
        8% { box-shadow: 0 0 18px rgba(197,177,248,0.85); border-color: #5b73d6; }
    }
    .cc-agent-tags { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 35px; }
    .cc-agent-tag {
        font-family: 'Roboto Mono', monospace; font-size: 0.75rem; color: #dbe4fb;
        border: 1px solid rgba(146, 190, 225, 0.15); border-radius: 999px; padding: 6px 14px;
    }
    .cc-mascot-small {
        display: flex; align-items: center; justify-content: center; height: 100%;
    }
    .cc-mascot-small img {
        max-width: 260px; width: 100%; height: auto;
        filter: drop-shadow(0 16px 30px rgba(0,0,0,0.5));
    }
    </style>
    """, unsafe_allow_html=True)

    # FIX: this used to be two separate st.columns([1,1]) — one holding the
    # radar (left-aligned in its column) and one holding the mascot image
    # (right-aligned in its column, via justify-content:flex-end). Column
    # gutters don't control the gap between the *content* inside each column,
    # only between the columns themselves — so with content pinned to the
    # outer edges, the visual gap between the radar and the mascot ended up
    # much wider than intended, and there was no way to move the mascot down
    # independently. Rendering both in a single flex row gives direct control
    # over both: `gap` sets the exact space between them, and the mascot
    # wrapper's `margin-top` shifts it down relative to the radar.
    encoded_cc_mascot = get_image_base64("assets/mascot1.png")
    mascot_img_html = (
        f'<img src="data:image/png;base64,{encoded_cc_mascot}" style="width:260px; max-width:100%;" />'
        if encoded_cc_mascot else '<div style="font-size:6rem;">🐙</div>'
    )
    st.markdown(f"""
    <div style="display:flex; align-items:center; justify-content:center; gap:28px; flex-wrap:wrap;">
        <div class="cc-radar">
            <div class="cc-radar-ring"></div>
            <div class="cc-radar-sweep"></div>
            <div class="cc-agent-node top">{security_icon_html}</div>
            <div class="cc-agent-node right">🚀</div>
            <div class="cc-agent-node bottom">🎨</div>
            <div class="cc-agent-node left">💬</div>
            <div class="cc-radar-center"><div class="pr-id">PR #482</div><div class="pr-status">analyzing…</div></div>
        </div>
        <div style="margin-top:70px;">{mascot_img_html}</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<div style='height:50px'></div>", unsafe_allow_html=True)
    # =========================================================================
    # STATS BAR
    # =========================================================================
    s1, s2, s3, s4 = st.columns(4, gap="large")
    for col, num, lbl in [
        (s1, "4", "Review Agents"),
        (s2, "100%", "Style Matched"),
        (s3, "24/7", "Webhook Triggered"),
        (s4, "0", "Unreviewed Merges"),
    ]:
        with col:
            st.markdown(f'<div class="stat-card"><div class="num">{num}</div><div class="lbl">{lbl}</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:50px'></div>", unsafe_allow_html=True)

    # =========================================================================
    # HOW IT WORKS
    # =========================================================================
    how_left, how_right = st.columns([1, 1.15], gap="large")
    with how_left:
        st.markdown("""
        <div>
            <div class="pai-tag">How it works</div>
            <h2 class="pai-h2">One integration. A full<br>review committee.</h2>
            <p class="pai-lead">Connect a repo once — a GitHub webhook picks up every new
            or updated PR automatically and walks it through the same pipeline, generating a
            clear summary before you decide.</p>
        </div>
        """, unsafe_allow_html=True)
    with how_right:
        steps = [
            ("Webhook fires on push", "A signed GitHub webhook notifies PrismAI the instant a PR opens or updates — no polling."),
            ("Fetch PR diff & metadata", "Pulls the changed files and surrounding context straight from GitHub."),
            ("Security & style agents run in parallel", "Flags vulnerabilities, lint issues, and convention drift."),
            ("Summarize & Report", "Generates a clear, readable summary of changes and potential impacts."),
            ("HITL breakpoint", "Pipeline pauses — you approve or reject the merge based on agent feedback."),
        ]
        rows = ""
        for i, (title, desc) in enumerate(steps, start=1):
            rows += f'<div class="step-row"><div class="step-num">{i}</div><div><h4>{title}</h4><p>{desc}</p></div></div>'
        st.markdown(f'<div class="content-glass">{rows}</div>', unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # =========================================================================
    # FEATURE GRID
    # =========================================================================
    st.markdown("""
    <div style="margin-bottom:24px;">
        <div class="pai-tag">Platform</div>
        <h2 class="pai-h2" style="margin-bottom:0 !important;">Everything a senior reviewer checks, automated</h2>
    </div>
    """, unsafe_allow_html=True)

    features = [
        ("🛡️", "Security Audit", "Catches injection risks, secrets, and unsafe patterns before merge."),
        ("🎨", "Style & Lint", "Keeps every PR consistent with your repo's conventions."),
        ("📝", "PR Summaries", "Transforms massive diffs into readable change reports."),
        ("🔍", "Logic Analysis", "Checks for common logical errors and missing edge cases."),
        ("🔌", "Webhook Auto-Trigger", "A signed GitHub webhook kicks off review the moment a PR opens or updates — nothing to poll."),
        ("⚖️", "HITL Approval", "Nothing merges without a human's final sign-off."),
        ("💬", "Chat With Your Repo", "Ask questions about your codebase; retrieval-augmented answers pull from your indexed files, with a live web fallback when local context runs dry."),
        ("📚", "Persistent History", "Every review thread and chat conversation is saved, so context carries across sessions."),
    ]
    f1, f2, f3 = st.columns(3, gap="large")
    for idx, (icon, title, desc) in enumerate(features):
        target = [f1, f2, f3][idx % 3]
        with target:
            st.markdown(
                f'<div class="feat-card"><span class="icon">{icon}</span><h4>{title}</h4><p>{desc}</p></div>',
                unsafe_allow_html=True,
            )
    st.markdown("<div style='height:50px'></div>", unsafe_allow_html=True)

    # =========================================================================
    # CHAT WITH YOUR REPO (CRAG)
    # =========================================================================
    chat_left, chat_right = st.columns([1, 1.1], gap="large")
    with chat_left:
        crag_steps = [
            ("Retrieve", "FAISS pulls the most relevant chunks from your indexed repo."),
            ("Grade", "Each chunk is scored for relevance to your question."),
            ("Route", "Strong matches go straight to the answer; weak ones trigger a web fallback."),
            ("Generate", "A grounded answer is written, citing where it came from."),
        ]
        rows = ""
        for i, (title, desc) in enumerate(crag_steps, start=1):
            rows += f'<div class="step-row"><div class="step-num">{i}</div><div><h4>{title}</h4><p>{desc}</p></div></div>'
        st.markdown(f"""
        <div>
            <div class="pai-tag">Talk to your codebase</div>
            <h2 class="pai-h2">Ask your repo a question.<br>Get a grounded answer.</h2>
            <p class="pai-lead">PrismAI indexes your repo with FAISS and retrieves the most
            relevant files for every question. When local context is thin, a corrective
            retrieval step reaches out to the web so answers stay accurate instead of guessing.</p>
            <div style="height:14px"></div>
            {rows}
        </div>
        """, unsafe_allow_html=True)

    with chat_right:
        st.markdown(f"""
        <div class="chat-glass-panel">
            <div class="chat-bubble user">Why does the webhook handler ignore duplicate deliveries?</div>
            <div class="chat-bubble agent">
                It checks the stored <code>github_comment_id</code> before posting — if one already
                exists for the PR, it updates that comment instead of creating a new one.
                <div>
                    <span class="chat-source-pill">repos.py</span>
                    <span class="chat-source-pill">webhook_handler.py</span>
                </div>
            </div>
            <div class="chat-bubble user">Is that from the repo or the web?</div>
            <div class="chat-bubble agent">
                Straight from your indexed repo — relevance score was high enough that no web
                fallback was needed.
                <div><span class="chat-source-pill">FAISS match · 0.87</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:50px'></div>", unsafe_allow_html=True)

    # =========================================================================
    # AGENT LINEUP
    # =========================================================================

    st.markdown("<div style='height:60px'></div>", unsafe_allow_html=True)
    st.markdown("""
    <div style="margin-bottom:24px;">
        <div class="pai-tag">Core capabilities</div>
        <h2 class="pai-h2" style="margin-bottom:0 !important;">One platform, four ways to review</h2>
    </div>
    """, unsafe_allow_html=True)

    capabilities = [
        ("🧩", "Multi-Agent PR Review", "Security, style, and summary agents run in parallel, then a human makes the final call."),
        ("💬", "CRAG Chat With Repo", "Ask your codebase questions — grounded in your indexed files, with a live web fallback when local context runs dry."),
        ("🔍", "Single PR Review", "Paste any PR link for an instant, one-off pass through the full agent pipeline."),
        ("🔌", "Automated Webhooks", "Connect a repo once — every new or updated PR is reviewed automatically, no polling."),
    ]
    cap_cols = st.columns(4, gap="large")
    for col, (icon, title, desc) in zip(cap_cols, capabilities):
        with col:
            st.markdown(
                f'<div class="feat-card"><span class="icon">{icon}</span><h4>{title}</h4><p>{desc}</p></div>',
                unsafe_allow_html=True,
            )
    st.markdown("<div style='height:60px'></div>", unsafe_allow_html=True)

    # =========================================================================
    # LANGSMITH OBSERVABILITY
    # =========================================================================
    ls_left, ls_mid, ls_right = st.columns([1, 1.15, 0.85], gap="large")
    with ls_left:
        st.markdown("""
        <div>
            <div class="pai-tag">Observability</div>
            <h2 class="pai-h2">Nothing runs in<br>a black box.</h2>
            <p class="pai-lead">Every agent call in the review pipeline is traced with
            LangSmith automatically — no manual instrumentation. If something looks off
            in a review, you can see exactly which step produced it.</p>
        </div>
        """, unsafe_allow_html=True)
    with ls_mid:
        langsmith_steps = [
            ("Every agent call traced", "Each LLM call, tool use, and retrieval step is logged the moment it runs."),
            ("Full run tree per PR", "See the complete Security, Performance, Style, and CRAG chain for any review, start to finish."),
            ("Debug failures fast", "Failed or slow runs surface with their exact inputs, outputs, and latency."),
            ("Prompt & cost visibility", "Track token usage and prompt versions across every review to keep runs efficient."),
        ]
        rows = ""
        for i, (title, desc) in enumerate(langsmith_steps, start=1):
            rows += f'<div class="step-row"><div class="step-num">{i}</div><div><h4>{title}</h4><p>{desc}</p></div></div>'
        st.markdown(f'<div class="content-glass">{rows}</div>', unsafe_allow_html=True)
    with ls_right:
        LANGSMITH_MASCOT_PATH = "assets/langsmith_mascot.png"
        encoded_ls_mascot = get_image_base64(LANGSMITH_MASCOT_PATH)
        if encoded_ls_mascot:
            st.markdown(f"""
<div class="ls-mascot-wrap"><img class="ls-mascot" src="data:image/png;base64,{encoded_ls_mascot}" alt="PrismAI observability engineer" /></div>
            """, unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    # =========================================================================
    # CTA BANNER
    # =========================================================================
    st.markdown("""
<div class="cta-banner">
    <h3>Connect your repo. Let agents take it from here.</h3>
    <p>Sign in with GitHub and review your first PR in minutes.</p>
</div>
    """, unsafe_allow_html=True)
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    cta_c1, cta_c2, cta_c3 = st.columns([1, 1, 1])
    with cta_c2:
        st.link_button("Review a PR✨", f"{BACKEND_URL}/auth/github/login", use_container_width=True)

    st.markdown('<div class="pai-footer">© 2026 PrismAI · LangGraph v3 · HITL Multi-Agent</div>', unsafe_allow_html=True)


def render_user_header_widget(theme: dict = None):
    u = st.session_state.get("github_user")
    if not u:
        return

    theme = theme or {}
    border_color = theme.get("border_color", "rgba(146, 190, 225, 0.35)")
    text_color = theme.get("text_color", "#e4e4e7")

    badge_col, logout_col = st.columns([2, 1])
    with badge_col:
        st.markdown(f"""
        <div style="display:flex;align-items:center;justify-content:flex-end;gap:8px;height:48px;">
            <span style="font-size:0.85rem;color:{text_color}99;">{u.get('login')}</span>
            <img src="{u.get('avatar_url')}" title="{u.get('login')}"
                 style="width:36px;height:36px;border-radius:50%;
                 border:2px solid {border_color};object-fit:cover;">
        </div>
        """, unsafe_allow_html=True)
    with logout_col:
        if st.button("\u23fb", key="header_logout_btn", help=f"Logout ({u.get('login')})"):
            session_id = st.session_state.get("prismai_session_id")
            try:
                if session_id:
                    requests.post(
                        f"{BACKEND_URL}/auth/logout",
                        cookies={"prismai_session": session_id},
                    )
            except requests.RequestException:
                pass
            st.session_state.github_user = None
            st.session_state.prismai_session_id = None
            st.rerun()