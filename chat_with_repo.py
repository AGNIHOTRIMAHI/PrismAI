"""
chat_with_repo.py
Renders a floating 💬 popover widget at the bottom-right.
Contains a mini-interface and a button to maximize to the full Chat page.
"""
import streamlit as st

def render_chat_widget(
    backend_url: str = "https://prismai-backend-nih2.onrender.com",
    btn_bg: str = "#9d4edd",
    shadow_color: str = "rgba(157,78,221,0.5)",
    repo_url: str = "",
    github_token: str = "",
):
    # Store repo context in session state
    st.session_state["chat_repo_url"] = repo_url
    st.session_state["chat_github_token"] = github_token
    st.session_state["chat_backend_url"] = backend_url

    # CSS to force the st.popover to float in the corner
    st.markdown(f"""
    <style>
    /* Float the entire popover container to the bottom right */
    div[data-testid="stPopover"] {{
        position: fixed !important;
        bottom: 28px !important;
        right: 28px !important;
        z-index: 9999 !important;
    }}
    
    /* Style the trigger button to look like a floating chat bubble */
    div[data-testid="stPopover"] > button {{
        width: 60px !important;
        height: 60px !important;
        border-radius: 50% !important;
        background-color: {btn_bg} !important;
        color: white !important;
        font-size: 1.8rem !important;
        border: 2px solid rgba(255,255,255,0.15) !important;
        box-shadow: 0 4px 20px {shadow_color} !important;
        padding: 0 !important;
        transition: transform 0.2s !important;
    }}
    div[data-testid="stPopover"] > button:hover {{
        transform: scale(1.08) !important;
        filter: brightness(1.2) !important;
    }}
    
    /* Style the interior panel of the popover */
    div[data-testid="stPopoverBody"] {{
        width: 320px !important;
        background-color: #250a47 !important;
        border: 1px solid #54199c !important;
        border-radius: 12px !important;
        padding: 15px !important;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5) !important;
    }}
    </style>
    """, unsafe_allow_html=True)

    # The Native Streamlit Popover
    with st.popover("💬"):
        st.markdown("#### 🟪 PrismAI Quick Chat")
        
        # Display current status
        if repo_url:
            st.caption(f"**Target:** `{repo_url.split('/')[-1]}`")
        else:
            st.warning("⚠️ No PR loaded yet.")

        st.divider()
        
        st.markdown("<p style='font-size: 0.9rem; color: #e4e4e7;'>Need deep insights, architectural explanations, or security details about this repository?</p>", unsafe_allow_html=True)
        
        # The Maximize Button
        if st.button("Maximize to Full Chat ↗️", use_container_width=True, type="primary"):
            st.switch_page("pages/1_Chat.py")