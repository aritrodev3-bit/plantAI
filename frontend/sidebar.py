import streamlit as st

from auth.database import revoke_session
from frontend.runtime import clear_auth_state


_SIDEBAR_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

#MainMenu, footer, header { visibility: hidden; }
div[data-testid="stSidebarNav"] { display: none !important; }
div[data-testid="collapsedControl"] { display: none !important; }

section[data-testid="stSidebar"] {
    display: block !important;
    width: 240px !important;
    min-width: 240px !important;
    background: #0f1a13 !important;
    border-right: 1px solid #1c3023 !important;
}

section[data-testid="stSidebar"] > div:first-child {
    padding: 0 !important;
}

.sb-logo {
    font-size: 1.2rem;
    font-weight: 700;
    letter-spacing: -0.5px;
    color: #f2f6f3;
    padding: 1.4rem 1.2rem 0.15rem 1.2rem;
    display: block;
}

.sb-logo span { color: #69c77b; }

.sb-tagline,
.sb-section,
.sb-user-label {
    font-size: 0.62rem;
    letter-spacing: 1.3px;
    text-transform: uppercase;
    color: #87a392;
    display: block;
}

.sb-tagline { padding: 0 1.2rem 1.1rem 1.2rem; }
.sb-section { padding: 0 1.2rem 0.55rem 1.2rem; font-weight: 600; }

.sb-divider {
    border: none;
    border-top: 1px solid #1c3023;
    margin: 0 1rem 0.9rem 1rem;
}

section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {
    display: flex !important;
    align-items: center !important;
    padding: 0.65rem 1rem !important;
    margin: 0.08rem 0.45rem !important;
    border-radius: 12px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.86rem !important;
    font-weight: 500 !important;
    color: #b7c8bd !important;
    text-decoration: none !important;
    border-left: 3px solid transparent !important;
    transition: background 0.15s ease, color 0.15s ease !important;
}

section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"],
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] *,
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] p,
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] span {
    color: #c9d8ce !important;
}

section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover {
    background: rgba(255, 255, 255, 0.06) !important;
    color: #f2f6f3 !important;
}

section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover *,
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover p,
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover span {
    color: #f2f6f3 !important;
}

section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] {
    background: rgba(91, 222, 138, 0.16) !important;
    border-left-color: #69c77b !important;
    color: #ecfff0 !important;
}

section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] *,
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] p,
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][aria-current="page"] span {
    color: #ecfff0 !important;
    font-weight: 600 !important;
}

section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] svg {
    display: none !important;
}

.sb-user-card {
    background: #132119;
    border: 1px solid #243b2c;
    border-radius: 12px;
    padding: 0.8rem 0.9rem;
    margin: 0 0.8rem 0.55rem 0.8rem;
}

.sb-username {
    font-size: 0.88rem;
    color: #f2f6f3;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

section[data-testid="stSidebar"] div[data-testid="stButton"] > button {
    background: transparent !important;
    color: #d2ddd6 !important;
    border: 1px solid #314a39 !important;
    border-radius: 10px !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    width: 100% !important;
    margin-top: 0.35rem !important;
}

section[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
    color: #ffd5d0 !important;
    border-color: #87463c !important;
    background: rgba(198, 40, 40, 0.14) !important;
    transform: none !important;
}

/* Hide every possible Streamlit collapse/expand toggle selector (covers 1.40–1.55) */
button[data-testid="collapsedControl"],
div[data-testid="stSidebarCollapseButton"],
div[data-testid="collapsedControl"],
button[kind="header"],
[data-testid="baseButton-headerNoPadding"] {
    display: none !important;
    visibility: hidden !important;
    pointer-events: none !important;
}

/* Force sidebar open — overrides any display:none/visibility:hidden from login page */
section[data-testid="stSidebar"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
}
</style>
"""


_NAV_ITEMS = [
    {"icon": "◻", "label": "Dashboard", "page": "pages/1_Dashboard.py"},
    {"icon": "◎", "label": "Analyse", "page": "pages/2_Analyse.py"},
    {"icon": "≡", "label": "History", "page": "pages/3_History.py"},
    {"icon": "⬒", "label": "Reports", "page": "pages/4_Reports.py"},
    {"icon": "◌", "label": "Profile", "page": "pages/5_Profile.py"},
]


def render_sidebar(active_page: str) -> None:
    st.session_state["active_page"] = active_page
    st.markdown(_SIDEBAR_CSS, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown(
            """
<span class="sb-logo">Plant<span>AI</span></span>
<span class="sb-tagline">Leaf disease detection</span>
<hr class="sb-divider">
<span class="sb-section">Navigation</span>
""",
            unsafe_allow_html=True,
        )

        for item in _NAV_ITEMS:
            st.page_link(item["page"], label=f"{item['icon']}  {item['label']}", use_container_width=True)

        st.markdown(
            """
<hr class="sb-divider" style="margin-top:0.9rem;">
<span class="sb-section">Account</span>
""",
            unsafe_allow_html=True,
        )

        user = st.session_state.get("user", {}) or {}
        username = user.get("username", "—")
        st.markdown(
            f"""
<div class="sb-user-card">
  <div class="sb-user-label">Signed in as</div>
  <div class="sb-username">🌿 {username}</div>
</div>
""",
            unsafe_allow_html=True,
        )

        if st.button("Log out", key="sb_logout"):
            token = st.session_state.get("session_token")
            if token:
                revoke_session(token)
            clear_auth_state()
            st.switch_page("app.py")
