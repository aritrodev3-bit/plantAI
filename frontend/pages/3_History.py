"""
frontend/pages/3_History.py
────────────────────────────
📁 Save as: PLANTDISEASEPROJ/frontend/pages/3_History.py

Scan history — filterable table, expandable remedy rows, CSV export.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import io
import json
import base64
import csv
from datetime import datetime

import streamlit as st
from PIL import Image

from frontend.db import get_scans, delete_scan
from frontend.runtime import require_login
from frontend.sidebar import render_sidebar
from frontend.ui import format_timestamp, inject_shared_styles

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="History · PlantAI",
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

.page-title {
    font-size: 1.45rem;
    font-weight: 600;
    color: #f0f0f0;
    letter-spacing: -0.4px;
    margin-bottom: 0.2rem;
}
.page-sub {
    font-size: 0.8rem;
    color: #444;
    margin-bottom: 1.8rem;
}

/* ── Filter bar ── */
.filter-bar {
    background: #141414;
    border: 1px solid #1f1f1f;
    border-radius: 14px;
    padding: 1rem 1.2rem;
    margin-bottom: 1.4rem;
}

/* ── Streamlit input overrides ── */
div[data-testid="stTextInput"] input,
div[data-testid="stSelectbox"] > div,
div[data-testid="stDateInput"] input {
    background: #0d0d0d !important;
    border: 1px solid #2a2a2a !important;
    border-radius: 8px !important;
    color: #e8e8e8 !important;
    font-size: 0.84rem !important;
}
div[data-testid="stTextInput"] input:focus {
    border-color: #5bde8a !important;
    box-shadow: 0 0 0 2px #5bde8a18 !important;
}

/* ── Table header ── */
.tbl-header {
    display: grid;
    grid-template-columns: 52px 1fr 110px 100px 90px 170px 70px;
    gap: 0.5rem;
    align-items: center;
    padding: 0.4rem 1rem;
    font-size: 0.62rem;
    font-weight: 500;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    color: #333;
    border-bottom: 1px solid #1a1a1a;
    margin-bottom: 0.3rem;
}

/* ── Scan row card ── */
.scan-card {
    background: #141414;
    border: 1px solid #1f1f1f;
    border-radius: 12px;
    margin-bottom: 0.4rem;
    overflow: hidden;
    transition: border-color 0.15s;
}
.scan-card:hover { border-color: #2a2a2a; }

.scan-row-grid {
    display: grid;
    grid-template-columns: 52px 1fr 110px 100px 90px 170px 70px;
    gap: 0.5rem;
    align-items: center;
    padding: 0.7rem 1rem;
}
.scan-thumb {
    width: 40px;
    height: 40px;
    border-radius: 8px;
    object-fit: cover;
    background: #1f1f1f;
}
.scan-thumb-placeholder {
    width: 40px;
    height: 40px;
    border-radius: 8px;
    background: #1a1a1a;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.1rem;
}
.scan-disease {
    font-size: 0.84rem;
    color: #e0e0e0;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.scan-conf {
    font-family: 'DM Mono', monospace;
    font-size: 0.8rem;
    font-weight: 500;
}
.scan-conf.green  { color: #5bde8a; }
.scan-conf.yellow { color: #f5c842; }
.scan-conf.red    { color: #f5665d; }
.scan-ts {
    font-size: 0.74rem;
    color: #444;
}

/* ── Pills ── */
.pill {
    display: inline-block;
    padding: 0.18rem 0.6rem;
    border-radius: 99px;
    font-size: 0.68rem;
    font-weight: 500;
    white-space: nowrap;
}
.pill.sev-low    { background: #1a3d28; color: #5bde8a; }
.pill.sev-medium { background: #3d3217; color: #f5c842; }
.pill.sev-high   { background: #3d1a1a; color: #f5665d; }

/* ── Remedy expand area ── */
.remedy-expand {
    background: #0f0f0f;
    border-top: 1px solid #1a1a1a;
    padding: 1.2rem 1.4rem;
}
.remedy-card {
    background: #141414;
    border: 1px solid #1f1f1f;
    border-radius: 14px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 0.8rem;
}
.remedy-section-title {
    font-size: 0.62rem;
    font-weight: 500;
    letter-spacing: 1.4px;
    text-transform: uppercase;
    color: #444;
    margin-bottom: 0.65rem;
}
.remedy-overview {
    font-size: 0.85rem;
    color: #aaa;
    line-height: 1.65;
}
.remedy-item {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    padding: 0.35rem 0;
    font-size: 0.82rem;
    color: #ccc;
    border-bottom: 1px solid #1c1c1c;
    line-height: 1.4;
}
.remedy-item:last-child { border-bottom: none; }
.remedy-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #5bde8a;
    margin-top: 0.35rem;
    flex-shrink: 0;
}
.remedy-dot.yellow { background: #f5c842; }
.remedy-dot.blue   { background: #5bc8de; }
.expert-box {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-left: 3px solid #f5c842;
    border-radius: 10px;
    padding: 0.8rem 1rem;
    font-size: 0.82rem;
    color: #aaa;
    line-height: 1.5;
}

/* ── Buttons ── */
div[data-testid="stButton"] > button {
    background: transparent !important;
    color: #5bde8a !important;
    border: 1px solid #2a4a38 !important;
    border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    padding: 0.3rem 0.8rem !important;
    width: auto !important;
    transition: background 0.15s !important;
}
div[data-testid="stButton"] > button:hover {
    background: rgba(91,222,138,0.06) !important;
    transform: none !important;
}

/* ── Empty state ── */
.empty-state {
    background: #141414;
    border: 1px solid #1f1f1f;
    border-radius: 16px;
    padding: 3.5rem 2rem;
    text-align: center;
}
.empty-icon { font-size: 2.2rem; margin-bottom: 0.8rem; }
.empty-msg  { font-size: 0.88rem; color: #444; margin-bottom: 1rem; }

/* ── Footer bar ── */
.footer-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 1rem;
    padding-top: 0.8rem;
    border-top: 1px solid #1a1a1a;
}
.footer-count {
    font-size: 0.75rem;
    color: #333;
    font-family: 'DM Mono', monospace;
}

/* Delete button — red variant */
button[data-testid*="del_"] {
    color: #f5665d !important;
    border-color: #4a2020 !important;
}
button[data-testid*="del_"]:hover {
    background: rgba(245,102,93,0.06) !important;
}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
inject_shared_styles("1200px")
render_sidebar("history")

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
    if conf >= 80:
        return "green"
    if conf >= 50: 
        return "yellow"
    return "red"


def severity_class(sev: str) -> str:
    return {"Low": "sev-low", "Medium": "sev-medium", "High": "sev-high"}.get(sev, "sev-medium")


def blob_to_b64(blob: bytes) -> str:
    try:
        img = Image.open(io.BytesIO(blob)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def format_ts(raw_ts: str) -> str:
    try:
        dt = datetime.strptime(raw_ts, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%b %-d, %Y · %-I:%M %p")
    except Exception:
        return raw_ts


def render_remedy_expanded(remedy: dict) -> None:
    """Render full remedy card inside the expandable row."""
    severity  = remedy.get("severity", "Medium")
    sev_class = {"Low": "sev-low", "Medium": "sev-medium", "High": "sev-high"}.get(severity, "sev-medium")

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:1rem;">
      <span style="font-size:0.65rem;font-weight:500;letter-spacing:1.4px;
                   text-transform:uppercase;color:#444;">Health Guide</span>
      <span class="pill {sev_class}">⚠ {severity} Severity</span>
    </div>
    """, unsafe_allow_html=True)

    # Overview
    st.markdown(f"""
    <div class="remedy-card">
      <div class="remedy-section-title">Overview</div>
      <div class="remedy-overview">{remedy.get("overview", "No overview available.")}</div>
    </div>
    """, unsafe_allow_html=True)

    # 3-column grid
    rc1, rc2, rc3 = st.columns(3, gap="small")
    with rc1:
        items = "".join([
            f'<div class="remedy-item"><div class="remedy-dot"></div><div>{i}</div></div>'
            for i in remedy.get("remedies", [])
        ])
        st.markdown(f"""
        <div class="remedy-card" style="height:100%;">
          <div class="remedy-section-title">💊 Remedies</div>
          {items or '<div style="color:#333;font-size:0.8rem;">None listed.</div>'}
        </div>
        """, unsafe_allow_html=True)
    with rc2:
        items = "".join([
            f'<div class="remedy-item"><div class="remedy-dot yellow"></div><div>{i}</div></div>'
            for i in remedy.get("dietary_tips", [])
        ])
        st.markdown(f"""
        <div class="remedy-card" style="height:100%;">
          <div class="remedy-section-title">🌱 Soil & Nutrition</div>
          {items or '<div style="color:#333;font-size:0.8rem;">None listed.</div>'}
        </div>
        """, unsafe_allow_html=True)
    with rc3:
        items = "".join([
            f'<div class="remedy-item"><div class="remedy-dot blue"></div><div>{i}</div></div>'
            for i in remedy.get("lifestyle_steps", [])
        ])
        st.markdown(f"""
        <div class="remedy-card" style="height:100%;">
          <div class="remedy-section-title">🔄 Prevention</div>
          {items or '<div style="color:#333;font-size:0.8rem;">None listed.</div>'}
        </div>
        """, unsafe_allow_html=True)

    # Expert box
    st.markdown(f"""
    <div class="expert-box">
      <strong style="color:#f5c842;">🩺 When to consult an expert</strong><br>
      {remedy.get("when_to_see_expert", "Consult an agronomist if symptoms worsen.")}
    </div>
    """, unsafe_allow_html=True)


def scans_to_csv(scans: list[dict]) -> bytes:
    """Convert scan list to UTF-8 CSV bytes for download."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "timestamp", "filename", "predicted_class",
        "confidence", "severity"
    ])
    for s in scans:
        writer.writerow([
            s.get("id", ""),
            s.get("timestamp", ""),
            s.get("filename", ""),
            s.get("predicted_class", ""),
            s.get("confidence", ""),
            s.get("severity", ""),
        ])
    return buf.getvalue().encode("utf-8")


# ── Data ──────────────────────────────────────────────────────────────────────
username = st.session_state["user"]["username"]
all_scans = get_scans(username)

# ── Page header ───────────────────────────────────────────────────────────────
def format_ts(raw_ts: str) -> str:
    return format_timestamp(raw_ts)

st.markdown(f"""
<div class="page-title">History</div>
<div class="page-sub">{len(all_scans)} total scan{'s' if len(all_scans) != 1 else ''} on record</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# FILTERS
# ══════════════════════════════════════════════════════════════════════════════
with st.container():
    st.markdown('<div class="filter-bar">', unsafe_allow_html=True)
    f1, f2, f3, f4, f5 = st.columns([2, 1.4, 1.4, 1.2, 0.8])

    with f1:
        search_q = st.text_input(
            "Search", placeholder="Disease name…",
            key="hist_search", label_visibility="collapsed"
        )
    with f2:
        from_date = st.date_input(
            "From", value=None, key="hist_from",
            label_visibility="collapsed"
        )
    with f3:
        to_date = st.date_input(
            "To", value=None, key="hist_to",
            label_visibility="collapsed"
        )
    with f4:
        sev_filter = st.selectbox(
            "Severity", options=["All", "Low", "Medium", "High"],
            key="hist_sev", label_visibility="collapsed"
        )
    with f5:
        st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)
        if st.button("Clear", key="hist_clear"):
            st.session_state["hist_search"] = ""
            st.session_state["hist_from"]   = None
            st.session_state["hist_to"]     = None
            st.session_state["hist_sev"]    = "All"
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# ── Apply filters ─────────────────────────────────────────────────────────────
filtered = all_scans

if search_q:
    q = search_q.lower()
    filtered = [
        s for s in filtered
        if q in clean_label(s["predicted_class"]).lower()
        or q in s["predicted_class"].lower()
    ]

if from_date:
    filtered = [
        s for s in filtered
        if s["timestamp"][:10] >= str(from_date)
    ]

if to_date:
    filtered = [
        s for s in filtered
        if s["timestamp"][:10] <= str(to_date)
    ]

if sev_filter != "All":
    filtered = [
        s for s in filtered
        if (s.get("severity") or "Medium") == sev_filter
    ]

# ══════════════════════════════════════════════════════════════════════════════
# TABLE
# ══════════════════════════════════════════════════════════════════════════════

# ── Empty state ───────────────────────────────────────────────────────────────
if not all_scans:
    st.markdown("""
    <div class="empty-state">
      <div class="empty-icon">🌿</div>
      <div class="empty-msg">No scans yet. Analyse a leaf to build your history.</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Go to Analyse →", key="hist_goto_analyse"):
        st.switch_page("pages/2_Analyse.py")
    st.stop()

if not filtered:
    st.markdown("""
    <div class="empty-state">
      <div class="empty-icon">🔍</div>
      <div class="empty-msg">No scans match your filters.</div>
    </div>
    """, unsafe_allow_html=True)
else:
    # ── Column headers ────────────────────────────────────────────────────────
    st.markdown("""
    <div class="tbl-header">
      <div></div>
      <div>Disease</div>
      <div>Confidence</div>
      <div>Severity</div>
      <div style="text-align:right">Conf %</div>
      <div>Timestamp</div>
      <div></div>
    </div>
    """, unsafe_allow_html=True)

    # ── Rows ──────────────────────────────────────────────────────────────────
    # Track which row is expanded via session state
    if "hist_expanded" not in st.session_state:
        st.session_state["hist_expanded"] = set()
    if "hist_confirm_del" not in st.session_state:
        st.session_state["hist_confirm_del"] = None

    for scan in filtered:
        scan_id    = scan["id"]
        pred_raw   = scan["predicted_class"]
        pred_label = clean_label(pred_raw)
        conf       = scan["confidence"]
        conf_cls   = confidence_color(conf)
        sev        = scan.get("severity") or "Medium"
        sev_cls    = severity_class(sev)
        ts         = format_ts(scan["timestamp"])
        is_open    = scan_id in st.session_state["hist_expanded"]

        # Thumbnail HTML
        if scan.get("image_blob"):
            b64 = blob_to_b64(scan["image_blob"])
            thumb_html = f'<img class="scan-thumb" src="{b64}" alt="">' if b64 else \
                         '<div class="scan-thumb-placeholder">🌿</div>'
        else:
            thumb_html = '<div class="scan-thumb-placeholder">🌿</div>'

        # Row card
        st.markdown(f"""
        <div class="scan-card">
          <div class="scan-row-grid">
            {thumb_html}
            <div class="scan-disease">{pred_label}</div>
            <div style="font-size:0.75rem;color:#555;">{pred_raw.split("___")[0] if "___" in pred_raw else ""}</div>
            <span class="pill {sev_cls}">{sev}</span>
            <div class="scan-conf {conf_cls}" style="text-align:right">{conf}%</div>
            <div class="scan-ts">{ts}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Action buttons row
        btn_c1, btn_c2, btn_c3 = st.columns([1, 1, 6])
        with btn_c1:
            expand_label = "▲ Hide" if is_open else "▼ View"
            if st.button(expand_label, key=f"expand_{scan_id}"):
                if is_open:
                    st.session_state["hist_expanded"].discard(scan_id)
                else:
                    st.session_state["hist_expanded"].add(scan_id)
                st.rerun()
        with btn_c2:
            if st.button("🗑 Delete", key=f"del_{scan_id}"):
                st.session_state["hist_confirm_del"] = scan_id
                st.rerun()

        # Delete confirmation
        if st.session_state["hist_confirm_del"] == scan_id:
            st.warning(f"Delete **{pred_label}** from {ts}? This cannot be undone.")
            conf_c1, conf_c2 = st.columns([1, 5])
            with conf_c1:
                if st.button("Yes, delete", key=f"confirm_del_{scan_id}"):
                    delete_scan(scan_id)
                    st.session_state["hist_confirm_del"] = None
                    st.session_state["hist_expanded"].discard(scan_id)
                    st.rerun()
            with conf_c2:
                if st.button("Cancel", key=f"cancel_del_{scan_id}"):
                    st.session_state["hist_confirm_del"] = None
                    st.rerun()

        # Expandable remedy card — lazy parsed
        if is_open:
            remedy_json = scan.get("remedy_json", "{}")
            try:
                remedy = json.loads(remedy_json) if remedy_json else {}
            except Exception:
                remedy = {}

            with st.container():
                st.markdown('<div class="remedy-expand">', unsafe_allow_html=True)
                if remedy and "overview" in remedy:
                    render_remedy_expanded(remedy)
                else:
                    st.markdown("""
                    <div style="color:#444;font-size:0.83rem;padding:0.5rem 0;">
                      No remedy data saved for this scan.
                    </div>
                    """, unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# FOOTER — count + CSV export
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

foot_l, foot_r = st.columns([3, 1])
with foot_l:
    st.markdown(f"""
    <div class="footer-count">
      Showing {len(filtered)} of {len(all_scans)} scan{'s' if len(all_scans) != 1 else ''}
    </div>
    """, unsafe_allow_html=True)
with foot_r:
    if filtered:
        csv_bytes = scans_to_csv(filtered)
        st.download_button(
            label="⬇ Export CSV",
            data=csv_bytes,
            file_name=f"PlantAI_History_{username}.csv",
            mime="text/csv",
            key="hist_csv_export",
        )
