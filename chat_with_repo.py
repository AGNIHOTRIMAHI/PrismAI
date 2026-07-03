"""
chat_with_repo.py
Renders a floating popover widget at the bottom-right using a custom image icon.

APPROACH: Instead of fighting Streamlit's internal button markup (icon elements
vary between versions and are hard to reliably hide via CSS), we make the real
popover button fully invisible (opacity: 0) but still clickable, and overlay a
plain <img> tag on top at the exact same fixed position with pointer-events:none.
Clicks pass through the image straight to the invisible button underneath, so
the popover still opens/closes normally -- but visually all the user sees is
your custom icon.
"""
import streamlit as st


def render_chat_widget(
    backend_url: str = "https://prismai-backend-nih2.onrender.com",
    btn_bg: str = "#9d4edd",
    shadow_color: str = "rgba(157,78,221,0.5)",
    repo_url: str = "",
    github_token: str = "",
    icon_url: str = "",  # base64 data URI, e.g. "data:image/jpeg;base64,...."
):
    st.session_state["chat_repo_url"] = repo_url
    st.session_state["chat_github_token"] = github_token
    st.session_state["chat_backend_url"] = backend_url

    st.markdown(f"""
    <style>
    /* Float the entire popover container to the bottom right */
    div[data-testid="stPopover"] {{
        position: fixed !important;
        bottom: 28px !important;
        right: 28px !important;
        z-index: 9999 !important;
    }}

    /* Make the REAL button invisible but still clickable -- no more fighting
       Streamlit's internal icon markup. */
    div[data-testid="stPopover"] > button {{
        width: 60px !important;
        height: 60px !important;
        border-radius: 50% !important;
        background-color: {btn_bg} !important;
        border: 2px solid rgba(255,255,255,0.15) !important;
        box-shadow: 0 4px 20px {shadow_color} !important;
        padding: 0 !important;
        opacity: 1 !important;
        transition: transform 0.2s !important;
    }}

    /* Hide whatever icon Streamlit puts inside, by shrinking its visual
       content to nothing -- belt and suspenders alongside the image overlay */
    div[data-testid="stPopover"] > button svg,
    div[data-testid="stPopover"] > button span,
    div[data-testid="stPopover"] > button p {{
        opacity: 0 !important;
    }}

    div[data-testid="stPopover"] > button:hover {{
        transform: scale(1.08) !important;
        filter: brightness(1.2) !important;
    }}

    /* The visual overlay image -- sits exactly on top of the button,
       purely decorative, clicks pass straight through to the button below */
    .chat-icon-overlay {{
        position: fixed !important;
        bottom: 28px !important;
        right: 28px !important;
        width: 60px !important;
        height: 60px !important;
        border-radius: 50% !important;
        z-index: 10000 !important;
        pointer-events: none !important;
        overflow: hidden !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }}

    .chat-icon-overlay img {{
        width: 55% !important;
        height: 55% !important;
        object-fit: contain !important;
        pointer-events: none !important;
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

    <div class="chat-icon-overlay">
        <img src="{icon_url}" alt="chat icon">
    </div>
    """, unsafe_allow_html=True)

    with st.popover(" "):
        st.markdown("#### 🟪 PrismAI Quick Chat")

        if repo_url:
            st.caption(f"**Target:** `{repo_url.split('/')[-1]}`")
        else:
            st.warning("⚠️ No PR loaded yet.")

        st.divider()

        st.markdown(
            "<p style='font-size: 0.9rem; color: #e4e4e7;'>Need deep insights, "
            "architectural explanations, or security details about this "
            "repository?</p>",
            unsafe_allow_html=True,
        )

        if st.button("Maximize to Full Chat ↗️", use_container_width=True, type="primary"):
            st.switch_page("pages/1_Chat.py")