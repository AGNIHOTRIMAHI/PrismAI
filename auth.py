import streamlit as st
import streamlit.components.v1 as components
import requests
import base64
import os

from dotenv import load_dotenv

load_dotenv()



BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


def init_auth_state():
    if "auth_checked" not in st.session_state:
        st.session_state.auth_checked = False
    if "github_user" not in st.session_state:
        st.session_state.github_user = None

def check_login_status():
    """
    Calls the backend /auth/me endpoint, forwarding the browser's HttpOnly
    session cookie so FastAPI can resolve who's logged in.
    """
    try:
        cookies = dict(st.context.cookies) if hasattr(st, "context") else {}
        resp = requests.get(f"{BACKEND_URL}/auth/me", cookies=cookies, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("logged_in"):
                st.session_state.github_user = data.get("user")
                return True
    except Exception:
        pass
    st.session_state.github_user = None
    return False

def is_logged_in() -> bool:
    return st.session_state.get("github_user") is not None

def get_image_base64(filepath):
    """Reads a local image/video and returns a base64 string, or '' if missing."""
    try:
        with open(filepath, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return ""

def render_landing_page(theme: dict):
    bg_color = theme.get("bg_color", "#080212")
    text_color = theme.get("text_color", "#e4e4e7")
    panel_bg = theme.get("panel_bg", "#250a47")
    border_color = theme.get("border_color", "#54199c")
    shadow_color = theme.get("shadow_color", "rgba(157,78,221,0.7)")
    title_color = theme.get("title_color", "#f4f4f5")
    btn_bg = theme.get("btn_bg", "#9d4edd")

    # =========================================================================
    # ASSET SLOT #1 -- CENTRAL PRISM IMAGE OR VIDEO
    # -------------------------------------------------------------------------
    # Drop your prism/crystal asset in your project's assets/ folder and
    # point this filename at it. Supports a static image (jpeg/png) OR a
    # looping video (mp4/webm).
    #
    # If you're using a VIDEO instead of an image, see the "VIDEO VARIANT"
    # comment block further down in the HTML -- swap the prism-rotate div
    # for a <video> tag there.
    # =========================================================================
    PRISM_ASSET_PATH = "assets/image.png"   # CHANGE THIS to your filename
    encoded_prism = get_image_base64(PRISM_ASSET_PATH)
    prism_src = f"data:image/png;base64,{encoded_prism}" if encoded_prism else ""

    # ---- PAGE-LEVEL CSS (static styling -- always renders fine via st.markdown) ----
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Kavoon&family=Satisfy&family=Roboto+Mono:wght@400;700&family=Outfit:wght@300;400&display=swap');

/* 1. LOCK THE VIEWPORT & PREVENT SCROLLING */
html, body, [data-testid="stAppViewContainer"] {{
    overflow: hidden !important;
    height: 100vh !important;
    margin: 0;
    padding: 0;
}}

.block-container {{
    padding-top: 2rem !important;
    padding-bottom: 0rem !important;
    max-width: 95% !important;
}}

/* Dense Starfield Background */
.stApp {{ 

    background-color: {bg_color}; 

    background-image: 

        radial-gradient(1px 1px at 10% 10%, rgba(255,255,255,0.8) 100%, transparent),

        radial-gradient(2px 2px at 20% 30%, rgba(157,78,221,0.8) 100%, transparent),

        radial-gradient(1px 1px at 30% 80%, rgba(255,255,255,0.6) 100%, transparent),

        radial-gradient(2px 2px at 40% 20%, rgba(255,255,255,0.9) 100%, transparent),

        radial-gradient(1.5px 1.5px at 50% 50%, rgba(157,78,221,0.6) 100%, transparent),

        radial-gradient(1px 1px at 60% 90%, rgba(255,255,255,0.7) 100%, transparent),

        radial-gradient(2.5px 2.5px at 70% 10%, rgba(157,78,221,0.9) 100%, transparent),

        radial-gradient(1px 1px at 80% 60%, rgba(255,255,255,0.8) 100%, transparent),

        radial-gradient(2px 2px at 90% 40%, rgba(255,255,255,0.5) 100%, transparent),

        radial-gradient(1.5px 1.5px at 95% 85%, rgba(157,78,221,0.7) 100%, transparent);

    background-size: 200px 200px;

}}

/* RELAXED, SPACIOUS LEFT SIDE */
.split-left {{
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 20px 40px 20px 10px;
    height: 85vh; 
}}

.cursive-subheading {{
        font-family: 'Satisfy', cursive !important;
        font-size: 2.3rem !important;
        background: linear-gradient(90deg, #ffffff 0%, #cbd5e1 25%, #ffffff 50%, #cbd5e1 75%, #ffffff 100%)
       
        margin: 0px 0 15px 0 !important;
        font-weight: 600;
        letter-spacing: 0.6px;
        text-shadow: 0 0 8px rgba(192, 132, 252, 0.6);
        animation: textShimmer 4s linear infinite;
        filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.4));
}}

.pill-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 20px;
}}
.pill {{
    font-family: 'Roboto Mono', monospace;
    font-size: 0.8rem;
    padding: 6px 12px;
    border-radius: 999px;
    border: 1px solid {border_color};
    color: {text_color}cc;
    background: {panel_bg}55;
}}
.eyebrow-pill {{
    display: inline-block;
    font-family: 'Roboto Mono', monospace;
    font-size: 0.75rem;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    padding: 6px 14px;
    border-radius: 999px;
    border: 1px solid {border_color};
    color: {btn_bg};
    width: fit-content;
    margin-bottom: 18px;
}}
.landing-title {{
    font-family: 'Kavoon', cursive !important;
    font-size: 3.8rem !important;
    
    background: linear-gradient(135deg, {title_color} 0%, {btn_bg} 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0 0 5px 0!important;
    line-height: 1.1;
    letter-spacing: 1px;
    text-shadow: 0 0 8px rgba(157, 78, 221, 0.4);
}}
.landing-tagline {{
    color: {btn_bg} !important;
    font-weight: 700;
    letter-spacing: 2.5px;
    text-transform: uppercase;
    font-size: 0.85rem;
    margin: 0 0 20px 0 !important;
    font-family: 'Roboto Mono', monospace;
}}
.landing-subtext {{
    font-family: 'Space Grotesk', sans-serif !important;
    color: #cbd5e1 !important; /* Slightly brighter for better readability */
    font-size: 1.4rem;
    max-width: 460px;
    margin: 0 0 35px 0!important;
    line-height: 1.5;
    font-weight: 300;
    letter-spacing: 0.01em;
   
}}
.github-login-link {{
    display: inline-flex;
    align-items: center;
    gap: 10px;
    background: {btn_bg};
    color: #ffffff !important;
    font-weight: 600;
    font-size: 1.05rem;
    padding: 14px 30px;
    border-radius: 10px;
    text-decoration: none !important;
    transition: all 0.2s ease;
    width: fit-content;
    margin-top: 0 0 35px 0;
    box-shadow: 0 4px 15px {shadow_color};
}}
.github-login-link:hover {{
    filter: brightness(1.1);
    transform: translateY(-2px);
}}

/* SPACIOUS TERMINAL CONSOLE */
.terminal-container {{
    max-width: 460px;
    margin-top: 35px;
    background: rgba(10, 5, 20, 0.7);
    border-radius: 10px;
    border: 1px solid {border_color};
    overflow: hidden;
    backdrop-filter: blur(10px);
}}
.terminal-header {{
    display: flex;
    align-items: center;
    padding: 10px 14px;
    background: rgba(37, 10, 71, 0.5);
    border-bottom: 1px solid {border_color};
}}
.mac-dots {{ display: flex; gap: 6px; margin-right: 15px; }}
.dot {{ width: 10px; height: 10px; border-radius: 50%; }}
.dot.red {{ background: #ff5f56; }}
.dot.yellow {{ background: #ffbd2e; }}
.dot.green {{ background: #27c93f; }}
.terminal-title {{
    font-family: 'Roboto Mono', monospace;
    font-size: 11px;
    color: #8b949e;
}}
.terminal-body {{
    padding: 18px;
    font-family: 'Roboto Mono', monospace;
    font-size: 13px;
    color: #e2e8f0;
    line-height: 1.6;
}}

@keyframes blink {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: 0; }}
}}
@keyframes textShimmer {{
    0% {{
        background-position: 0% center;
    }}
    100% {{
        background-position: 200% center;
    }}
}}
.blinking-cursor {{
    display: inline-block;
    width: 4px;
    height: 16px; /* Gives the empty span a physical height */
    background-color: #c084fc !important; /* Uses background instead of text color */
    vertical-align: middle;
    box-shadow: 0 0 8px rgba(192, 132, 252, 0.8);
    animation: blink 1s step-end infinite;
    margin-left: 4px;

}}

/* RESPONSIVE DESIGN */
@media screen and (max-width: 992px) {{
    html, body, [data-testid="stAppViewContainer"] {{
        overflow-y: auto !important;
        height: auto !important;
    }}
    .split-left {{
        height: auto !important;
        text-align: center;
        align-items: center;
        padding: 40px 10px !important;
    }}
    .landing-subtext {{
        margin-left: auto;
        margin-right: auto;
    }}
    .pill-row {{
        justify-content: center;
    }}
    .terminal-container {{
        margin-left: auto;
        margin-right: auto;
        text-align: left;
    }}
}}
</style>
    """, unsafe_allow_html=True)

    # ---- SPLIT LAYOUT ----
    left_col, right_col = st.columns([1, 1.3], gap="large")

    with left_col:
        st.markdown(f"""
<div class="split-left">
        <h1 class="landing-title">PrismAI</h1>
        <div class="cursive-subheading">Autonomous PR Review Agent</div>
        <div class="landing-tagline" style="margin-bottom: 20px;">Refract &middot; Analyze &middot; Approve</div>
                
<p class="landing-subtext">
                    Navigate your codebase with confidence. Let PrismAI handle the heavy lifting, mapping out the complexities of every PR so you can focus on the mission ahead.
</p>

<a class="github-login-link" href="{BACKEND_URL}/auth/github/login" target="_self">
                    <svg height="20" viewBox="0 0 16 16" width="20" fill="currentColor" style="margin-right: 8px;">
                        <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
                    </svg>
                    Sign in with GitHub
</a>

<div class="terminal-container">
                    <div class="terminal-header">
                        <div class="mac-dots">
                            <div class="dot red"></div>
                            <div class="dot yellow"></div>
                            <div class="dot green"></div>
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
        components.html(f"""
        <div style="position:relative; width:100%; height:85vh; overflow:hidden;
                    background:radial-gradient(circle at 45% 50%, {panel_bg}66 0%, transparent 60%);
                    font-family:sans-serif;">

            <style>
                .dust {{ position:absolute; border-radius:50%; background:#ffffff;
                         animation: drift 6s ease-in-out infinite; pointer-events:none; }}
                @keyframes drift {{
                    0%, 100% {{ transform: translateY(0px); opacity:0.15; }}
                    50% {{ transform: translateY(-22px); opacity:0.55; }}
                }}

                /* BURST RAYS */
                .burst-ray {{
                    position:absolute; top:50%; left:45%;
                    width:2px; height:46%;
                    background:linear-gradient(to top, rgba(157,78,221,0.85), transparent 85%);
                    transform-origin: bottom center;
                    animation: rayPulse 3.2s ease-in-out infinite;
                }}
                @keyframes rayPulse {{
                    0%, 100% {{ opacity:0.25; }}
                    50% {{ opacity:0.85; }}
                }}

                .color-beam {{
                    position:absolute; top:50%; left:45%; height:3px;
                    transform-origin: left center;
                    border-radius:2px;
                    animation: beamGlow 4s ease-in-out infinite;
                }}
                @keyframes beamGlow {{
                    0%, 100% {{ opacity:0.35; filter:brightness(0.9); }}
                    50% {{ opacity:1; filter:brightness(1.3); }}
                }}

                .agent-label {{
                    position:absolute; font-family:'Roboto Mono',monospace;
                    font-size:12px; font-weight:700; letter-spacing:0.5px;
                    animation: labelFade 4s ease-in-out infinite;
                }}
                @keyframes labelFade {{
                    0%, 30% {{ opacity:0; }}
                    50%, 90% {{ opacity:1; }}
                    100% {{ opacity:0; }}
                }}

                .center-glow {{
                    position:absolute; top:50%; left:45%; width:140px; height:140px;
                    margin:-70px 0 0 -70px; border-radius:50%;
                    background:radial-gradient(circle, rgba(157,78,221,0.55) 0%, transparent 70%);
                    animation: glowPulse 3.2s ease-in-out infinite;
                }}
                @keyframes glowPulse {{
                    0%, 100% {{ transform:scale(0.9); opacity:0.6; }}
                    50% {{ transform:scale(1.15); opacity:1; }}
                }}

                .prism-rotate {{
                    position:absolute; top:50%; left:45%;
                    width:230px; height:230px;
                    margin:-115px 0 0 -115px;
                    animation: spin 14s linear infinite;
                    filter: drop-shadow(0 0 30px {shadow_color});
                }}
                @keyframes spin {{
                    from {{ transform: rotate(0deg); }}
                    to {{ transform: rotate(360deg); }}
                }}
                .prism-rotate img {{
                    width:100%; height:100%; object-fit:contain;
                    mix-blend-mode: screen; 
                }}

                /* Make the animations center perfectly when stacked on small screens */
                @media screen and (max-width: 992px) {{
                    .burst-ray, .color-beam, .center-glow, .prism-rotate {{
                        left: 50% !important;
                    }}
                }}
            </style>

            <div class="dust" style="width:3px;height:3px;top:12%;left:18%;animation-delay:0s;"></div>
            <div class="dust" style="width:4px;height:4px;top:30%;left:75%;animation-delay:1.2s;"></div>
            <div class="dust" style="width:2px;height:2px;top:60%;left:10%;animation-delay:0.6s;"></div>
            <div class="dust" style="width:3px;height:3px;top:75%;left:65%;animation-delay:2s;"></div>
            <div class="dust" style="width:2px;height:2px;top:20%;left:50%;animation-delay:1.6s;"></div>

            <div class="burst-ray" style="transform:translate(-50%,-100%) rotate(0deg);"></div>
            <div class="burst-ray" style="transform:translate(-50%,-100%) rotate(30deg);"></div>
            <div class="burst-ray" style="transform:translate(-50%,-100%) rotate(60deg);"></div>
            <div class="burst-ray" style="transform:translate(-50%,-100%) rotate(90deg);"></div>
            <div class="burst-ray" style="transform:translate(-50%,-100%) rotate(120deg);"></div>
            <div class="burst-ray" style="transform:translate(-50%,-100%) rotate(150deg);"></div>
            <div class="burst-ray" style="transform:translate(-50%,-100%) rotate(180deg);"></div>
            <div class="burst-ray" style="transform:translate(-50%,-100%) rotate(210deg);"></div>
            <div class="burst-ray" style="transform:translate(-50%,-100%) rotate(240deg);"></div>
            <div class="burst-ray" style="transform:translate(-50%,-100%) rotate(270deg);"></div>
            <div class="burst-ray" style="transform:translate(-50%,-100%) rotate(300deg);"></div>
            <div class="burst-ray" style="transform:translate(-50%,-100%) rotate(330deg);"></div>

            <div class="color-beam" style="width:45%; background:linear-gradient(to right, rgba(239,68,68,0.9), transparent); transform:translateY(-50%) rotate(-20deg);"></div>
            <div class="color-beam" style="width:50%; background:linear-gradient(to right, rgba(245,158,11,0.9), transparent); transform:translateY(-50%) rotate(0deg);"></div>
            <div class="color-beam" style="width:45%; background:linear-gradient(to right, rgba(16,185,129,0.9), transparent); transform:translateY(-50%) rotate(20deg);"></div>

            <div class="agent-label" style="color:#ef4444; top:35%; right:8%; animation-delay:0.1s; font-size:12px">Security</div>
            <div class="agent-label" style="color:#f59e0b; top:49%; right:2%; animation-delay:0.3s; font-size:12px">Style</div>
            <div class="agent-label" style="color:#10b981; top:63%; right:8%; animation-delay:0.5s; font-size:12px">Performance</div>

            <div class="center-glow"></div>

            <div class="prism-rotate">
                {f'<img src="{prism_src}" alt="" />' if prism_src else ''}
            </div>

        </div>
        """, height=800, scrolling=False)

def render_user_header_widget(theme: dict = None):
    """
    Compact horizontal avatar + logout, meant to sit in the header row
    next to the dark/light mode toggle (NOT the sidebar).
    """
    u = st.session_state.get("github_user")
    if not u:
        return

    border_color = (theme or {}).get("border_color", "#54199c")
    text_color = (theme or {}).get("text_color", "#e4e4e7")

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
            try:
                cookies = dict(st.context.cookies) if hasattr(st, "context") else {}
                requests.post(f"{BACKEND_URL}/auth/logout", cookies=cookies)
            except Exception:
                pass
            st.session_state.github_user = None
            st.rerun()
