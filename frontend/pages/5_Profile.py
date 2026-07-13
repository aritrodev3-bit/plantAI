"""
frontend/pages/5_Profile.py
────────────────────────────
📁 Save as: PLANTDISEASEPROJ/frontend/pages/5_Profile.py

Profile page — user info, stats, donut chart, danger zone, logout.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
import plotly.graph_objects as go  # pyright: ignore[reportMissingImports]

from frontend.db import delete_all_scans, get_scans, get_stats
from frontend.runtime import clear_auth_state, require_login
from frontend.sidebar import render_sidebar
from frontend.ui import inject_shared_styles

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Profile · PlantAI",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Auth check ────────────────────────────────────────────────────────────────
require_login()

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif !important;
    background-color: #0d0d0d !important;
    color: #e8e8e8 !important;
}
#MainMenu, footer, header { visibility: hidden; }
section[data-testid="stSidebar"] { width: 220px !important; }

.main .block-container {
    padding-top: 2rem !important;
    padding-bottom: 3rem !important;
    max-width: 1000px !important;
}

.page-title {
    font-size: 1.45rem;
    font-weight: 600;
    color: #f0f0f0;
    letter-spacing: -0.4px;
    margin-bottom: 0.2rem;
}
.page-sub { font-size: 0.8rem; color: #444; margin-bottom: 1.8rem; }

/* ── Avatar card ── */
.avatar-card {
    background: #141414;
    border: 1px solid #1f1f1f;
    border-radius: 16px;
    padding: 1.8rem 1.6rem;
    text-align: center;
    margin-bottom: 1rem;
}
.avatar-circle {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    background: linear-gradient(135deg, #1a3d28, #2a5a3a);
    border: 2px solid #2d6b45;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 0.9rem auto;
    font-size: 1.5rem;
    font-weight: 700;
    color: #5bde8a;
    font-family: 'DM Sans', sans-serif;
    letter-spacing: -0.5px;
}
.avatar-name {
    font-size: 1.15rem;
    font-weight: 600;
    color: #f0f0f0;
    margin-bottom: 0.2rem;
}
.avatar-scan-count {
    font-family: 'DM Mono', monospace;
    font-size: 0.75rem;
    color: #444;
}

/* ── Stat cards ── */
.stat-card {
    background: #141414;
    border: 1px solid #1f1f1f;
    border-radius: 14px;
    padding: 1.1rem 1.3rem;
    margin-bottom: 0.7rem;
}
.stat-label {
    font-size: 0.62rem;
    font-weight: 500;
    letter-spacing: 1.3px;
    text-transform: uppercase;
    color: #444;
    margin-bottom: 0.35rem;
}
.stat-value {
    font-size: 1rem;
    font-weight: 600;
    color: #e0e0e0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.stat-value.green  { color: #5bde8a; }
.stat-value.yellow { color: #f5c842; }

/* ── Chart card ── */
.chart-card {
    background: #141414;
    border: 1px solid #1f1f1f;
    border-radius: 14px;
    padding: 1.2rem 1.4rem 0.4rem 1.4rem;
    margin-bottom: 0.7rem;
}
.chart-title {
    font-size: 0.62rem;
    font-weight: 500;
    letter-spacing: 1.3px;
    text-transform: uppercase;
    color: #444;
    margin-bottom: 0.5rem;
}

/* ── Danger zone ── */
.danger-card {
    background: #141414;
    border: 1px solid #3d1a1a;
    border-radius: 14px;
    padding: 1.3rem 1.5rem;
    margin-top: 1.4rem;
}
.danger-title {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: #f5665d;
    margin-bottom: 0.4rem;
}
.danger-desc {
    font-size: 0.82rem;
    color: #555;
    margin-bottom: 1rem;
    line-height: 1.5;
}

/* ── Buttons ── */
div[data-testid="stButton"] > button {
    background: transparent !important;
    color: #5bde8a !important;
    border: 1px solid #2a4a38 !important;
    border-radius: 10px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.84rem !important;
    font-weight: 500 !important;
    width: 100% !important;
    transition: background 0.15s !important;
}
div[data-testid="stButton"] > button:hover {
    background: rgba(91,222,138,0.06) !important;
    transform: none !important;
}

/* Logout button — muted */
.logout-wrap div[data-testid="stButton"] > button {
    color: #555 !important;
    border-color: #1f1f1f !important;
}
.logout-wrap div[data-testid="stButton"] > button:hover {
    color: #f5665d !important;
    border-color: #4a2020 !important;
    background: rgba(245,102,93,0.05) !important;
}

/* Text input */
div[data-testid="stTextInput"] input {
    background: #0d0d0d !important;
    border: 1px solid #3d1a1a !important;
    border-radius: 8px !important;
    color: #e8e8e8 !important;
    font-size: 0.84rem !important;
    font-family: 'DM Mono', monospace !important;
}
div[data-testid="stTextInput"] input:focus {
    border-color: #f5665d !important;
    box-shadow: 0 0 0 2px #f5665d18 !important;
}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
inject_shared_styles("1000px")
render_sidebar("profile")

# ── Data ──────────────────────────────────────────────────────────────────────
user     = st.session_state["user"]
username = user["username"]
email    = user.get("email", "")
stats    = get_stats(username)
scans    = get_scans(username)

total_scans     = stats["total_scans"]
healthy_count   = round(total_scans * stats["healthy_rate"] / 100) if total_scans else 0
diseased_count  = total_scans - healthy_count

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="page-title">Profile</div>
<div class="page-sub">Your account overview and scan statistics</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# LAYOUT — left column (avatar + stats) | right column (donut + danger zone)
# ══════════════════════════════════════════════════════════════════════════════
left_col, right_col = st.columns([1, 1.6], gap="medium")

# ── LEFT ──────────────────────────────────────────────────────────────────────
with left_col:

    # Avatar card
    initials = username[:2].upper()
    st.markdown(f"""
    <div class="avatar-card">
      <div class="avatar-circle">{initials}</div>
      <div class="avatar-name">{username}</div>
      <div class="avatar-scan-count">{total_scans} scan{"s" if total_scans != 1 else ""} on record</div>
    </div>
    """, unsafe_allow_html=True)

    # Stat cards
    most_scanned_plant = "—"
    if scans:
        from collections import Counter
        plants = [s["predicted_class"].split("___")[0].replace("_", " ").strip()
                  for s in scans]
        most_scanned_plant = Counter(plants).most_common(1)[0][0]

    st.markdown(f"""
    <div class="stat-card">
      <div class="stat-label">Most Scanned Plant</div>
      <div class="stat-value">{most_scanned_plant}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="stat-card">
      <div class="stat-label">Most Common Disease</div>
      <div class="stat-value">{stats["most_common_disease"]}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="stat-card">
      <div class="stat-label">Avg Confidence</div>
      <div class="stat-value green">{stats["avg_confidence"]}%</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="stat-card">
      <div class="stat-label">Healthy Rate</div>
      <div class="stat-value yellow">{stats["healthy_rate"]}%</div>
    </div>
    """, unsafe_allow_html=True)

    # Logout
    st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
    st.markdown('<div class="logout-wrap">', unsafe_allow_html=True)
    if st.button("Log out", key="profile_logout"):
        try:
            from auth.database import revoke_session
            token = st.session_state.get("session_token")
            if token:
                revoke_session(token)
        except Exception:
            pass
        clear_auth_state()
        st.switch_page("app.py")
    st.markdown("</div>", unsafe_allow_html=True)

# ── RIGHT ─────────────────────────────────────────────────────────────────────
with right_col:

    # Donut chart — Healthy vs Diseased
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown('<div class="chart-title">Healthy vs Diseased</div>', unsafe_allow_html=True)

    if total_scans > 0:
        fig_donut = go.Figure(go.Pie(
            labels=["Healthy", "Diseased"],
            values=[healthy_count, diseased_count],
            hole=0.62,
            marker=dict(
                colors=["#5bde8a", "#f5665d"],
                line=dict(color="#0d0d0d", width=2),
            ),
            textinfo="none",
            hovertemplate="%{label}: %{value} scan(s) (%{percent})<extra></extra>",
        ))
        fig_donut.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="DM Sans", color="#888888", size=11),
            margin=dict(l=0, r=0, t=8, b=8),
            height=240,
            showlegend=True,
            legend=dict(
                font=dict(color="#888", size=11),
                bgcolor="rgba(0,0,0,0)",
                orientation="h",
                x=0.5, xanchor="center",
                y=-0.05,
            ),
            annotations=[dict(
                text=f"<b>{total_scans}</b><br><span style='font-size:10px'>total</span>",
                x=0.5, y=0.5,
                font=dict(size=18, color="#f0f0f0", family="DM Sans"),
                showarrow=False,
            )],
        )
        st.plotly_chart(fig_donut, use_container_width=True, config={"displayModeBar": False})
    else:
        st.markdown("""
        <div style="height:240px;display:flex;align-items:center;
                    justify-content:center;color:#333;font-size:0.84rem;">
          No scan data yet
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Danger zone ───────────────────────────────────────────────────────────
    st.markdown("""
    <div class="danger-card">
      <div class="danger-title">⚠ Danger Zone</div>
      <div class="danger-desc">
        Permanently delete all your scans and history.
        This action cannot be undone.
        Type <strong style="color:#f0f0f0;font-family:'DM Mono',monospace;">DELETE</strong> to confirm.
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Confirmation input + button inside the card visually
    confirm_input = st.text_input(
        "Type DELETE to confirm",
        key="profile_delete_confirm",
        placeholder="DELETE",
        label_visibility="collapsed",
    )

    # Session state for delete feedback
    if "profile_delete_done" not in st.session_state:
        st.session_state["profile_delete_done"] = False

    btn_disabled = confirm_input.strip() != "DELETE"

    if st.button(
        "Delete all my scans",
        key="profile_delete_btn",
        disabled=btn_disabled,
    ):
        if total_scans == 0:
            st.info("You have no scans to delete.")
        else:
            delete_all_scans(username)
            st.session_state["profile_delete_confirm"] = ""
            st.session_state["profile_delete_done"] = True
            st.rerun()

    if st.session_state["profile_delete_done"]:
        st.success("✓ All scans deleted successfully.")
        st.session_state["profile_delete_done"] = False
