"""
frontend/pages/1_Dashboard.py
──────────────────────────────
📁 Save as: PLANTDISEASEPROJ/frontend/pages/1_Dashboard.py

Dashboard page — live stat cards, plotly charts, recent scans table.
All data pulled from SQLite via db.py — zero hardcoded values.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import io
import base64
from datetime import datetime

import streamlit as st
import plotly.graph_objects as go # pyright: ignore[reportMissingImports]
from PIL import Image

from frontend.db import get_scans, get_stats
from frontend.runtime import require_login
from frontend.sidebar import render_sidebar
from frontend.ui import format_timestamp, inject_shared_styles

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Dashboard · PlantAI",
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
    max-width: 1200px !important;
}

/* ── Page title ── */
.dash-title {
    font-size: 1.45rem;
    font-weight: 600;
    color: #f0f0f0;
    letter-spacing: -0.4px;
    margin-bottom: 0.2rem;
}
.dash-sub {
    font-size: 0.8rem;
    color: #444;
    margin-bottom: 2rem;
}

/* ── Stat cards ── */
.stat-card {
    background: #141414;
    border: 1px solid #1f1f1f;
    border-radius: 16px;
    padding: 1.4rem 1.6rem;
    height: 100%;
}
.stat-label {
    font-size: 0.65rem;
    font-weight: 500;
    letter-spacing: 1.4px;
    text-transform: uppercase;
    color: #444;
    margin-bottom: 0.5rem;
}
.stat-value {
    font-size: 2rem;
    font-weight: 600;
    color: #f0f0f0;
    line-height: 1.1;
    letter-spacing: -0.5px;
}
.stat-value.green  { color: #5bde8a; }
.stat-value.yellow { color: #f5c842; }
.stat-value.blue   { color: #5bc8de; }
.stat-sub {
    font-family: 'DM Mono', monospace;
    font-size: 0.7rem;
    color: #333;
    margin-top: 0.3rem;
}

/* ── Chart cards ── */
.chart-card {
    background: #141414;
    border: 1px solid #1f1f1f;
    border-radius: 16px;
    padding: 1.4rem 1.6rem 0.5rem 1.6rem;
}
.chart-title {
    font-size: 0.65rem;
    font-weight: 500;
    letter-spacing: 1.4px;
    text-transform: uppercase;
    color: #444;
    margin-bottom: 0.8rem;
}

/* ── Recent scans table ── */
.section-title {
    font-size: 0.65rem;
    font-weight: 500;
    letter-spacing: 1.4px;
    text-transform: uppercase;
    color: #444;
    margin-bottom: 1rem;
    margin-top: 0.5rem;
}
.scan-row {
    display: flex;
    align-items: center;
    gap: 1rem;
    background: #141414;
    border: 1px solid #1f1f1f;
    border-radius: 12px;
    padding: 0.75rem 1.1rem;
    margin-bottom: 0.5rem;
}
.scan-thumb {
    width: 40px;
    height: 40px;
    border-radius: 8px;
    object-fit: cover;
    flex-shrink: 0;
    background: #1f1f1f;
}
.scan-disease {
    flex: 1;
    font-size: 0.84rem;
    color: #e0e0e0;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.scan-conf {
    font-family: 'DM Mono', monospace;
    font-size: 0.78rem;
    min-width: 52px;
    text-align: right;
}
.scan-conf.green  { color: #5bde8a; }
.scan-conf.yellow { color: #f5c842; }
.scan-conf.red    { color: #f5665d; }
.scan-ts {
    font-size: 0.72rem;
    color: #333;
    min-width: 130px;
    text-align: right;
}
.pill {
    display: inline-block;
    padding: 0.18rem 0.65rem;
    border-radius: 99px;
    font-size: 0.68rem;
    font-weight: 500;
    letter-spacing: 0.3px;
    white-space: nowrap;
}
.pill.sev-low    { background: #1a3d28; color: #5bde8a; }
.pill.sev-medium { background: #3d3217; color: #f5c842; }
.pill.sev-high   { background: #3d1a1a; color: #f5665d; }
.pill.healthy    { background: #1a3d28; color: #5bde8a; }
.pill.diseased   { background: #3d1a1a; color: #f5665d; }

/* ── Empty state ── */
.empty-state {
    background: #141414;
    border: 1px solid #1f1f1f;
    border-radius: 16px;
    padding: 3rem 2rem;
    text-align: center;
    color: #333;
}
.empty-icon { font-size: 2rem; margin-bottom: 0.75rem; }
.empty-msg  { font-size: 0.88rem; color: #444; }

/* ── Action buttons ── */
div[data-testid="stButton"] > button {
    background: transparent !important;
    color: #5bde8a !important;
    border: 1px solid #2a4a38 !important;
    border-radius: 10px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    transition: background 0.15s !important;
}
div[data-testid="stButton"] > button:hover {
    background: rgba(91,222,138,0.06) !important;
    transform: none !important;
}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
inject_shared_styles("1200px")
render_sidebar("dashboard")

# ── Data ──────────────────────────────────────────────────────────────────────
user     = st.session_state["user"]
username = user["username"]
stats    = get_stats(username)
scans    = get_scans(username)


# ── Helpers ───────────────────────────────────────────────────────────────────

def clean_label(raw: str) -> str:
    parts = raw.split("___")
    if len(parts) == 2:
        plant, condition = parts
        plant     = plant.replace("_", " ").replace(",", "").strip()
        condition = condition.replace("_", " ").strip()
        return f"{condition} ({plant})"
    return raw.replace("_", " ")


def confidence_color(conf: float) -> str:
    if conf >= 80:   return "green"
    if conf >= 50:   return "yellow"
    return "red"


def severity_class(sev: str) -> str:
    return {"Low": "sev-low", "Medium": "sev-medium", "High": "sev-high"}.get(sev, "sev-medium")


def blob_to_b64(blob: bytes) -> str:
    """Convert raw image bytes to a base64 data URI for inline HTML."""
    try:
        img = Image.open(io.BytesIO(blob)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def format_ts(raw_ts: str) -> str:
    """'2026-03-18 21:41:00'  →  'Mar 18, 2026 · 9:41 PM'"""
    try:
        dt = datetime.strptime(raw_ts, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%b %-d, %Y · %-I:%M %p")
    except Exception:
        return raw_ts


# ── Page header ───────────────────────────────────────────────────────────────
def format_ts(raw_ts: str) -> str:
    return format_timestamp(raw_ts)

st.markdown(f"""
<div class="dash-title">Dashboard</div>
<div class="dash-sub">Welcome back, {username} — here's your plant health overview</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# ROW 1 — Stat cards
# ══════════════════════════════════════════════════════════════════════════════
c1, c2, c3, c4 = st.columns(4, gap="small")

with c1:
    st.markdown(f"""
    <div class="stat-card">
      <div class="stat-label">Total Scans</div>
      <div class="stat-value blue">{stats['total_scans']}</div>
      <div class="stat-sub">all time</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="stat-card">
      <div class="stat-label">Unique Diseases</div>
      <div class="stat-value yellow">{stats['unique_diseases']}</div>
      <div class="stat-sub">detected</div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="stat-card">
      <div class="stat-label">Avg Confidence</div>
      <div class="stat-value green">{stats['avg_confidence']}%</div>
      <div class="stat-sub">model certainty</div>
    </div>
    """, unsafe_allow_html=True)

with c4:
    st.markdown(f"""
    <div class="stat-card">
      <div class="stat-label">Healthy Rate</div>
      <div class="stat-value">{stats['healthy_rate']}%</div>
      <div class="stat-sub">of scans</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# ROW 2 — Charts
# ══════════════════════════════════════════════════════════════════════════════
ch_left, ch_right = st.columns(2, gap="small")

# ── Left: Scans per day (bar chart) ──────────────────────────────────────────
with ch_left:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown('<div class="chart-title">Scans — Last 7 Days</div>', unsafe_allow_html=True)

    spd       = stats["scans_per_day"]
    day_keys  = list(spd.keys())
    day_vals  = list(spd.values())

    # Short labels: "Mon 18"
    try:
        day_labels = [
            datetime.strptime(d, "%Y-%m-%d").strftime("%a %-d")
            for d in day_keys
        ]
    except Exception:
        day_labels = day_keys

    fig_bar = go.Figure(go.Bar(
        x=day_labels,
        y=day_vals,
        marker_color="#5bde8a",
        marker_line_width=0,
        hovertemplate="%{x}: %{y} scan(s)<extra></extra>",
    ))
    fig_bar.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#141414",
        font=dict(family="DM Sans", color="#888888", size=11),
        margin=dict(l=0, r=0, t=8, b=0),
        height=220,
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            tickfont=dict(size=11, color="#555"),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#1f1f1f",
            zeroline=False,
            tickfont=dict(size=11, color="#555"),
            tickformat="d",
        ),
        bargap=0.35,
    )
    st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)

# ── Right: Top 5 diseases (horizontal bar) ────────────────────────────────────
with ch_right:
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown('<div class="chart-title">Top 5 Diseases Detected</div>', unsafe_allow_html=True)

    top = stats["top_diseases"]

    if top:
        names  = [d["name"] for d in reversed(top)]
        counts = [d["count"] for d in reversed(top)]

        fig_h = go.Figure(go.Bar(
            x=counts,
            y=names,
            orientation="h",
            marker_color="#5bde8a",
            marker_line_width=0,
            hovertemplate="%{y}: %{x} scan(s)<extra></extra>",
        ))
        fig_h.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#141414",
            font=dict(family="DM Sans", color="#888888", size=11),
            margin=dict(l=0, r=0, t=8, b=0),
            height=220,
            xaxis=dict(
                showgrid=True,
                gridcolor="#1f1f1f",
                zeroline=False,
                tickfont=dict(size=11, color="#555"),
                tickformat="d",
            ),
            yaxis=dict(
                showgrid=False,
                zeroline=False,
                tickfont=dict(size=11, color="#aaa"),
            ),
            bargap=0.35,
        )
        st.plotly_chart(fig_h, use_container_width=True, config={"displayModeBar": False})
    else:
        st.markdown("""
        <div style="height:220px;display:flex;align-items:center;
                    justify-content:center;color:#333;font-size:0.82rem;">
          No disease data yet
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# ROW 3 — Recent scans (last 5)
# ══════════════════════════════════════════════════════════════════════════════
hdr_l, hdr_r = st.columns([3, 1])
with hdr_l:
    st.markdown('<div class="section-title">Recent Scans</div>', unsafe_allow_html=True)
with hdr_r:
    if st.button("View All →", key="dash_view_all"):
        st.switch_page("pages/3_History.py")

recent = scans[:5]

if not recent:
    st.markdown("""
    <div class="empty-state">
      <div class="empty-icon">🌿</div>
      <div class="empty-msg">No scans yet — upload your first leaf image to get started.</div>
    </div>
    """, unsafe_allow_html=True)
else:
    for scan in recent:
        pred_raw   = scan["predicted_class"]
        pred_label = clean_label(pred_raw)
        conf       = scan["confidence"]
        conf_cls   = confidence_color(conf)
        sev        = scan.get("severity") or "Medium"
        sev_cls    = severity_class(sev)
        ts         = format_ts(scan["timestamp"])

        # Thumbnail
        thumb_html = ""
        if scan.get("image_blob"):
            b64 = blob_to_b64(scan["image_blob"])
            if b64:
                thumb_html = f'<img class="scan-thumb" src="{b64}" alt="thumb">'
        if not thumb_html:
            thumb_html = '<div class="scan-thumb" style="display:flex;align-items:center;justify-content:center;font-size:1.1rem;">🌿</div>'

        st.markdown(f"""
        <div class="scan-row">
          {thumb_html}
          <div class="scan-disease">{pred_label}</div>
          <span class="pill {sev_cls}">{sev}</span>
          <div class="scan-conf {conf_cls}">{conf}%</div>
          <div class="scan-ts">{ts}</div>
        </div>
        """, unsafe_allow_html=True)

# ── Quick Analyse button ───────────────────────────────────────────────────────
st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
_, btn_col, _ = st.columns([2, 1, 2])
with btn_col:
    if st.button("＋ Quick Analyse", key="dash_analyse"):
        st.switch_page("pages/2_Analyse.py")
