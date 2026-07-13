from runtime import ensure_project_root, init_session_state

ensure_project_root(__file__)

import streamlit as st

from auth.auth_ui import require_auth
from frontend.db import init_db


st.set_page_config(
    page_title="PlantAI",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session_state()
init_db()

# Hide sidebar on login page WITHOUT using display:none on the sidebar element.
# Using display:none on stSidebar persists in React state across st.switch_page()
# and causes the sidebar to remain hidden on all authenticated pages.
if not st.session_state.get("logged_in"):
    with st.sidebar:
        st.markdown("")  # Render empty sidebar so it collapses naturally

st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {{
    font-family: 'DM Sans', sans-serif !important;
    background-color: #0f1511 !important;
    color: #f2f6f3 !important;
}}

#MainMenu, footer, header {{ visibility: hidden; }}

/* On the login page, visually hide sidebar area without killing layout state */
{"section[data-testid='stSidebar'] { visibility: hidden; width: 0 !important; min-width: 0 !important; }" if not st.session_state.get('logged_in') else ""}

.main .block-container {{
    padding-top: 6vh !important;
    padding-bottom: 3rem !important;
    max-width: 980px !important;
}}

button[data-testid="collapsedControl"],
div[data-testid="stSidebarCollapseButton"] {{
    display: none !important;
}}

div[data-testid="stTextInput"] input {{
    background: #18201b !important;
    border: 1px solid #2b3931 !important;
    border-radius: 10px !important;
    color: #f2f6f3 !important;
    font-size: 0.88rem !important;
}}

div[data-testid="stTextInput"] input:focus {{
    border-color: #2e7d32 !important;
    box-shadow: 0 0 0 2px rgba(46, 125, 50, 0.12) !important;
}}

div[data-testid="stTabs"] button[role="tab"] {{
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    color: #9daf9f !important;
    background: transparent !important;
}}

div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {{
    color: #2e7d32 !important;
    border-bottom-color: #2e7d32 !important;
}}

div[data-testid="stButton"] > button[kind="primary"] {{
    background: #2e7d32 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    width: 100% !important;
    margin-top: 0.4rem !important;
}}

div[data-testid="stButton"] > button[kind="primary"]:hover {{
    opacity: 0.9 !important;
    transform: none !important;
}}
</style>
""",
    unsafe_allow_html=True,
)

require_auth()
st.switch_page("pages/1_Dashboard.py")
