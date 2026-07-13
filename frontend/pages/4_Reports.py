"""
frontend/pages/4_Reports.py
────────────────────────────
📁 Save as: PLANTDISEASEPROJ/frontend/pages/4_Reports.py

Reports page — select a past scan, preview it, generate + download a PDF.
Uses reportlab (Platypus + Canvas) for PDF generation.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import base64
import io
import json
from datetime import datetime

import streamlit as st
from PIL import Image

# ── ReportLab imports ─────────────────────────────────────────────────────────
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.platypus import (
        HRFlowable,
        Image as RLImage,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    REPORTLAB_ERROR = ""
except ImportError as exc:
    REPORTLAB_ERROR = str(exc)

from frontend.db import get_scans
from frontend.runtime import require_login
from frontend.sidebar import render_sidebar
from frontend.ui import format_timestamp, inject_shared_styles

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Reports · PlantAI",
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
    font-size: 1.45rem; font-weight: 600; color: #f0f0f0;
    letter-spacing: -0.4px; margin-bottom: 0.2rem;
}
.page-sub { font-size: 0.8rem; color: #444; margin-bottom: 1.8rem; }
.panel-card {
    background: #141414; border: 1px solid #1f1f1f;
    border-radius: 16px; padding: 1.4rem 1.6rem;
}
.panel-label {
    font-size: 0.62rem; font-weight: 500; letter-spacing: 1.4px;
    text-transform: uppercase; color: #444; margin-bottom: 1rem;
}
.diag-card {
    background: #0d0d0d; border: 1px solid #1f1f1f;
    border-radius: 12px; padding: 1rem 1.2rem; margin-bottom: 0.7rem;
}
.diag-label {
    font-size: 0.62rem; font-weight: 500; letter-spacing: 1.2px;
    text-transform: uppercase; color: #444; margin-bottom: 0.3rem;
}
.diag-value         { font-size: 1.1rem; font-weight: 600; color: #f0f0f0; }
.diag-value.green   { color: #5bde8a; }
.diag-value.yellow  { color: #f5c842; }
.diag-value.red     { color: #f5665d; }
.diag-sub { font-family:'DM Mono',monospace; font-size:0.72rem; color:#333; margin-top:0.2rem; }
.pill { display:inline-block; padding:0.2rem 0.7rem; border-radius:99px; font-size:0.7rem; font-weight:500; }
.pill.sev-low    { background:#1a3d28; color:#5bde8a; }
.pill.sev-medium { background:#3d3217; color:#f5c842; }
.pill.sev-high   { background:#3d1a1a; color:#f5665d; }
.remedy-card {
    background:#0d0d0d; border:1px solid #1f1f1f;
    border-radius:12px; padding:1rem 1.2rem; margin-bottom:0.7rem;
}
.remedy-section-title {
    font-size:0.62rem; font-weight:500; letter-spacing:1.2px;
    text-transform:uppercase; color:#444; margin-bottom:0.6rem;
}
.remedy-overview { font-size:0.84rem; color:#aaa; line-height:1.65; }
.remedy-item {
    display:flex; align-items:flex-start; gap:0.5rem;
    padding:0.35rem 0; font-size:0.81rem; color:#ccc;
    border-bottom:1px solid #1c1c1c; line-height:1.4;
}
.remedy-item:last-child { border-bottom:none; }
.remedy-dot { width:5px; height:5px; border-radius:50%; background:#5bde8a; margin-top:0.38rem; flex-shrink:0; }
.remedy-dot.yellow { background:#f5c842; }
.remedy-dot.blue   { background:#5bc8de; }
.expert-box {
    background:#141414; border:1px solid #2a2a2a;
    border-left:3px solid #f5c842; border-radius:10px;
    padding:0.8rem 1rem; font-size:0.82rem; color:#aaa; line-height:1.5;
}
div[data-testid="stSelectbox"] > div {
    background:#141414 !important; border:1px solid #2a2a2a !important;
    border-radius:10px !important; color:#e8e8e8 !important; font-size:0.84rem !important;
}
div[data-testid="stButton"] > button,
div[data-testid="stDownloadButton"] > button {
    background:#5bde8a !important; color:#0d0d0d !important;
    border:none !important; border-radius:10px !important;
    font-family:'DM Sans',sans-serif !important; font-size:0.88rem !important;
    font-weight:600 !important; width:100% !important; transition:opacity 0.15s !important;
}
div[data-testid="stButton"] > button:hover,
div[data-testid="stDownloadButton"] > button:hover {
    opacity:0.88 !important; transform:none !important;
}
.empty-state {
    background:#141414; border:1px solid #1f1f1f;
    border-radius:16px; padding:3.5rem 2rem; text-align:center;
}
.empty-msg { font-size:0.88rem; color:#444; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
inject_shared_styles("1200px")
render_sidebar("reports")

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


def format_ts(raw_ts: str) -> str:
    try:
        dt = datetime.strptime(raw_ts, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%b %-d, %Y · %-I:%M %p")
    except Exception:
        return raw_ts


def format_ts_pdf(raw_ts: str) -> str:
    try:
        dt = datetime.strptime(raw_ts, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%B %d, %Y at %I:%M %p UTC")
    except Exception:
        return raw_ts


def blob_to_pil(blob: bytes) -> Image.Image | None:
    try:
        return Image.open(io.BytesIO(blob)).convert("RGB")
    except Exception:
        return None


# ── ReportLab colour palette ──────────────────────────────────────────────────
# ── PDF colour palette (white background safe) ───────────────────────────────
C_BG     = colors.HexColor("#0d0d0d")
C_CARD   = colors.HexColor("#141414")
C_CARD2  = colors.HexColor("#1a1a1a")
C_BORDER = colors.HexColor("#dddddd")   # light grey rule lines on white PDF
C_BORDER2= colors.HexColor("#cccccc")
C_TEXT   = colors.HexColor("#1a1a1a")   # near-black for body text
C_MUTED  = colors.HexColor("#444444")   # dark grey for secondary text
C_DIM    = colors.HexColor("#888888")   # medium grey for labels/footer
C_DIM2   = colors.HexColor("#666666")   # header subtitle
C_GREEN  = colors.HexColor("#1a8a4a")   # darker green — readable on white
C_YELLOW = colors.HexColor("#b07d00")   # darker yellow/amber — readable on white
C_RED    = colors.HexColor("#c0392b")   # darker red — readable on white
C_WHITE  = colors.HexColor("#ffffff")   # white text for dark headers
C_BLUE   = colors.HexColor("#1a6a8a")   # darker blue — readable on white


# ── Custom canvas — draws header + footer on every page ───────────────────────

def _make_chrome_painter(username: str, gen_ts: str):
    """
    Returns an onPage callback (canvas, doc) -> None.
    Passed to doc.build() as both onFirstPage and onLaterPages.
    Avoids subclassing Canvas entirely — no _startPage / PropertySet issues.
    """
    def paint(c: rl_canvas.Canvas, doc) -> None:
        w, h = A4
        c.saveState()

        # ── Header background ────────────────────────────────────────────────
        c.setFillColor(colors.HexColor("#141414"))
        c.rect(0, h - 26 * mm, w, 26 * mm, fill=1, stroke=0)

        # "PlantAI" in white
        c.setFont("Helvetica-Bold", 17)
        c.setFillColor(C_WHITE)
        c.drawString(18 * mm, h - 13 * mm, "PlantAI")

        # "  Disease Report" in green
        c.setFont("Helvetica", 10)
        c.setFillColor(C_GREEN)
        c.drawString(18 * mm + 52, h - 13 * mm, "  Disease Report")

        # Subtitle
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.HexColor("#aaaaaa"))   # light grey on dark header bar
        c.drawString(18 * mm, h - 20 * mm,
                     "Leaf disease detection  ·  EfficientNet-B0  ·  38 classes")

        # Header bottom border
        c.setStrokeColor(colors.HexColor("#2a2a2a"))
        c.setLineWidth(0.4)
        c.line(0, h - 26 * mm, w, h - 26 * mm)

        # ── Footer ────────────────────────────────────────────────────────────
        c.setStrokeColor(colors.HexColor("#2a2a2a"))
        c.setLineWidth(0.3)
        c.line(18 * mm, 13 * mm, w - 18 * mm, 13 * mm)

        c.setFont("Helvetica", 7)
        c.setFillColor(colors.HexColor("#888888"))
        footer = f"Generated by PlantAI  ·  {username}  ·  {gen_ts}"
        c.drawCentredString(w / 2, 8 * mm, footer)

        c.restoreState()

    return paint


# ── PDF builder ───────────────────────────────────────────────────────────────

def generate_pdf(scan: dict, remedy: dict, username: str) -> bytes:
    """Build a PlantAI report with ReportLab Platypus. Returns PDF bytes."""
    if REPORTLAB_ERROR:
        raise RuntimeError(
            "Report generation is unavailable because reportlab is not installed."
        )

    pred_raw   = scan.get("predicted_class", "Unknown")
    pred_label = clean_label(pred_raw)
    confidence = scan.get("confidence", 0.0)
    severity   = scan.get("severity", "Medium")
    timestamp  = scan.get("timestamp", "")
    ts_display = format_ts_pdf(timestamp)
    now_str    = datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC")

    buf = io.BytesIO()
    getSampleStyleSheet()

    # ── Style factory ─────────────────────────────────────────────────────────
    # textColor is set as an attribute AFTER construction to avoid the
    # ParagraphStyle type-checker error (parent expects PropertySet, not Color).
    def s(name: str, **kw) -> ParagraphStyle:
        text_color = kw.pop("textColor", C_TEXT)
        defaults = dict(fontName="Helvetica", fontSize=9, leading=14, spaceAfter=2)
        defaults.update(kw)
        ps = ParagraphStyle(name, **defaults) # type: ignore
        ps.textColor = text_color  # type: ignore[attr-defined]
        return ps

    s_ts       = s("ts",   fontSize=8,  textColor=C_DIM,   spaceAfter=10)
    s_section  = s("sec",  fontName="Helvetica-Bold", fontSize=7.5,
                   textColor=C_DIM, spaceBefore=8, spaceAfter=3, leading=10)
    s_disease  = s("dis",  fontName="Helvetica-Bold", fontSize=15,
                   textColor=C_WHITE, leading=20, spaceAfter=2)
    s_raw      = s("raw",  fontSize=8,  textColor=C_DIM,   spaceAfter=8)
    s_body     = s("body", fontSize=9,  textColor=C_MUTED, leading=15, spaceAfter=4)
    s_bullet   = s("bul",  fontSize=9,  textColor=C_TEXT,  leading=14,
                   leftIndent=12, bulletIndent=0, firstLineIndent=-6, spaceAfter=2)
    s_expert   = s("exp",  fontSize=9,  textColor=C_MUTED, leading=14,
                   leftIndent=6, spaceAfter=4)

    def section_block(title: str) -> list:
        return [
            Spacer(1, 4),
            Paragraph(title.upper(), s_section),
            HRFlowable(width="100%", thickness=0.4,
                       color=colors.HexColor("#dddddd"), spaceAfter=5),
        ]

    def bullet_items(items: list) -> list:
        return [Paragraph(item, s_bullet, bulletText="•") for item in items]

    story: list = []
    story.append(Paragraph(f"Scan date: {ts_display}", s_ts))

    # ── Section 1: Scan image ─────────────────────────────────────────────────
    # Pass image as BytesIO — avoids temp file timing issues on Windows where
    # ReportLab reads the file lazily during doc.build(), after os.unlink().
    if scan.get("image_blob"):
        img_pil = blob_to_pil(scan["image_blob"])
        if img_pil:
            try:
                img_buf = io.BytesIO()
                img_pil.save(img_buf, format="JPEG", quality=85)
                img_buf.seek(0)
                max_w  = 120 * mm
                ratio  = max_w / img_pil.width
                img_h  = img_pil.height * ratio
                rl_img = RLImage(img_buf, width=max_w, height=img_h)
                rl_img.hAlign = "CENTER"
                story.append(rl_img)
                story.append(Spacer(1, 8))
            except Exception:
                pass

    # ── Section 2: Diagnosis ──────────────────────────────────────────────────
    story += section_block("Diagnosis")
    story.append(Paragraph(pred_label, s_disease))
    story.append(Paragraph(pred_raw, s_raw))

    # Confidence & Severity side-by-side boxes
    conf_clr = C_GREEN if confidence >= 80 else C_YELLOW if confidence >= 50 else C_RED
    sev_clr  = C_GREEN if severity == "Low" else C_YELLOW if severity == "Medium" else C_RED

    conf_cell = Paragraph(
        f'<font name="Helvetica" size="7" color="#555555">CONFIDENCE</font><br/>'
        f'<font name="Helvetica-Bold" size="13" color="{conf_clr.hexval()}">{confidence}%</font>',
        s("cf", leading=18),
    )
    sev_cell = Paragraph(
        f'<font name="Helvetica" size="7" color="#555555">SEVERITY</font><br/>'
        f'<font name="Helvetica-Bold" size="13" color="{sev_clr.hexval()}">{severity}</font>',
        s("sv", leading=18),
    )
    diag_tbl = Table([[conf_cell, sev_cell]], colWidths=["50%", "50%"])
    diag_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, 0), colors.HexColor("#f5f5f5")),
        ("BACKGROUND",    (1, 0), (1, 0), colors.HexColor("#f5f5f5")),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEAFTER",     (0, 0), (0, -1), 0.4, colors.HexColor("#dddddd")),
        ("BOX",           (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
    ]))
    story.append(diag_tbl)
    story.append(Spacer(1, 10))

    # ── Section 3: Overview ───────────────────────────────────────────────────
    overview = remedy.get("overview", "")
    if overview:
        story += section_block("Overview")
        story.append(Paragraph(overview, s_body))

    # ── Section 4: Remedies ───────────────────────────────────────────────────
    remedies = remedy.get("remedies", [])
    if remedies:
        story += section_block("Remedies")
        story += bullet_items(remedies)
        story.append(Spacer(1, 4))

    # ── Section 5: Soil & Nutrition ───────────────────────────────────────────
    dietary = remedy.get("dietary_tips", [])
    if dietary:
        story += section_block("Soil & Nutrition")
        story += bullet_items(dietary)
        story.append(Spacer(1, 4))

    # ── Section 6: Prevention ─────────────────────────────────────────────────
    lifestyle = remedy.get("lifestyle_steps", [])
    if lifestyle:
        story += section_block("Prevention Steps")
        story += bullet_items(lifestyle)
        story.append(Spacer(1, 4))

    # ── Section 7: Expert consultation ───────────────────────────────────────
    expert = remedy.get("when_to_see_expert", "")
    if expert:
        story += section_block("When to Consult an Expert")
        expert_tbl = Table(
            [[Paragraph("", s("empty")), Paragraph(expert, s_expert)]],
            colWidths=[3, None],
        )
        expert_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#fffbf0")),
            ("LEFTPADDING",   (0, 0), (0, -1), 0),
            ("RIGHTPADDING",  (0, 0), (0, -1), 0),
            ("LEFTPADDING",   (1, 0), (1, -1), 8),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LINEBEFORE",    (0, 0), (0, -1), 3, colors.HexColor("#b07d00")),
            ("BOX",           (0, 0), (-1, -1), 0.4, colors.HexColor("#e0c060")),
        ]))
        story.append(expert_tbl)

    # ── Build ─────────────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=30 * mm,      # space for header bar
        bottomMargin=20 * mm,   # space for footer
        leftMargin=18 * mm,
        rightMargin=18 * mm,
    )

    chrome = _make_chrome_painter(username, now_str)
    doc.build(story, onFirstPage=chrome, onLaterPages=chrome)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# STREAMLIT UI
# ══════════════════════════════════════════════════════════════════════════════

def format_ts(raw_ts: str) -> str:
    return format_timestamp(raw_ts)

username  = st.session_state["user"]["username"]
all_scans = get_scans(username)

st.markdown("""
<div class="page-title">Reports</div>
<div class="page-sub">Select a past scan to preview and export as PDF</div>
""", unsafe_allow_html=True)

if REPORTLAB_ERROR:
    st.error(
        "PDF export needs `reportlab`. Install the updated requirements to enable reports."
    )
    st.stop()

if not all_scans:
    st.markdown("""
    <div class="empty-state">
      <div style="font-size:2rem;margin-bottom:0.8rem;">📄</div>
      <div class="empty-msg">No scans yet. Analyse a leaf first to generate a report.</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    if st.button("Go to Analyse →", key="rep_goto_analyse"):
        st.switch_page("pages/2_Analyse.py")
    st.stop()

# ── Layout ────────────────────────────────────────────────────────────────────
left_col, right_col = st.columns([1, 2], gap="medium")

with left_col:
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.markdown('<div class="panel-label">Select Scan</div>', unsafe_allow_html=True)

    def dropdown_label(s: dict) -> str:
        try:
            dt   = datetime.strptime(s["timestamp"], "%Y-%m-%d %H:%M:%S")
            date = dt.strftime("%b %-d, %Y")
        except Exception:
            date = s["timestamp"][:10]
        return f"{clean_label(s['predicted_class'])} — {date}"

    scan_labels  = [dropdown_label(s) for s in all_scans]
    selected_idx = st.selectbox(
        "Scan", options=range(len(scan_labels)),
        format_func=lambda i: scan_labels[i],
        key="rep_scan_select",
        label_visibility="collapsed",
    )

    selected_scan = all_scans[selected_idx]
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    remedy: dict = {}
    try:
        raw_json = selected_scan.get("remedy_json", "{}")
        remedy   = json.loads(raw_json) if raw_json else {}
    except Exception:
        remedy = {}

    pdf_bytes = generate_pdf(selected_scan, remedy, username)

    safe_disease = (
        selected_scan["predicted_class"]
        .replace("___", "_").replace(" ", "")[:40]
    )
    date_str = selected_scan["timestamp"][:10]
    filename = f"PlantAI_Report_{safe_disease}_{date_str}.pdf"

    st.download_button(
        label="⬇ Download PDF",
        data=pdf_bytes,
        file_name=filename,
        mime="application/pdf",
        key="rep_download",
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ── Right preview panel ───────────────────────────────────────────────────────
with right_col:
    pred_raw   = selected_scan["predicted_class"]
    pred_label = clean_label(pred_raw)
    conf       = selected_scan["confidence"]
    conf_cls   = confidence_color(conf)
    sev        = selected_scan.get("severity") or "Medium"
    sev_cls    = severity_class(sev)

    preview_html = [
        '<div class="panel-card">',
        '<div class="panel-label">Preview</div>',
    ]

    if selected_scan.get("image_blob"):
        img = blob_to_pil(selected_scan["image_blob"])
        if img:
            img_buf = io.BytesIO()
            img.save(img_buf, format="PNG")
            img_data = base64.b64encode(img_buf.getvalue()).decode("ascii")
            preview_html.append(
                '<div style="text-align:center;margin-bottom:0.8rem;">'
                f'<img src="data:image/png;base64,{img_data}" '
                'style="max-width:100%;height:auto;border-radius:12px;"/>'
                '</div>'
            )

    preview_html.append(f"""
    <div class="diag-card">
      <div class="diag-label">Detected Condition</div>
      <div class="diag-value">{pred_label}</div>
      <div class="diag-sub">{pred_raw}</div>
    </div>
    """)

    preview_html.append(
        '<div style="display:flex; gap:0.8rem; flex-wrap:wrap; margin-bottom:0.7rem;">'
        f'<div class="diag-card" style="flex:1; min-width:160px;">'
        '  <div class="diag-label">Confidence</div>'
        f'  <div class="diag-value {conf_cls}">{conf}%</div>'
        '</div>'
        f'<div class="diag-card" style="flex:1; min-width:160px;">'
        '  <div class="diag-label">Severity</div>'
        '  <div style="margin-top:0.4rem;">'
        f'    <span class="pill {sev_cls}">{sev}</span>'
        '  </div>'
        '</div>'
        '</div>'
    )

    if remedy and remedy.get("overview"):
        preview_html.append(f"""
        <div class="remedy-card">
          <div class="remedy-section-title">Overview</div>
          <div class="remedy-overview">{remedy.get("overview","")}</div>
        </div>
        """)

        preview_html.append('<div style="display:flex; gap:0.9rem; flex-wrap:wrap; margin-top:0.5rem;">')
        preview_html.append(
            '<div class="remedy-card" style="flex:1; min-width:170px;">'
            '  <div class="remedy-section-title">💊 Remedies</div>'
            f'  {"".join([f"<div class=\"remedy-item\"><div class=\"remedy-dot\"></div><div>{i}</div></div>" for i in remedy.get("remedies", [])]) or '<div style="color:#999;font-size:0.82rem;">None listed.</div>'}'
            '</div>'
        )
        preview_html.append(
            '<div class="remedy-card" style="flex:1; min-width:170px;">'
            '  <div class="remedy-section-title">🌱 Soil & Nutrition</div>'
            f'  {"".join([f"<div class=\"remedy-item\"><div class=\"remedy-dot yellow\"></div><div>{i}</div></div>" for i in remedy.get("dietary_tips", [])]) or '<div style="color:#999;font-size:0.82rem;">None listed.</div>'}'
            '</div>'
        )
        preview_html.append(
            '<div class="remedy-card" style="flex:1; min-width:170px;">'
            '  <div class="remedy-section-title">🔄 Prevention</div>'
            f'  {"".join([f"<div class=\"remedy-item\"><div class=\"remedy-dot blue\"></div><div>{i}</div></div>" for i in remedy.get("lifestyle_steps", [])]) or '<div style="color:#999;font-size:0.82rem;">None listed.</div>'}'
            '</div>'
        )
        preview_html.append('</div>')

        preview_html.append(f"""
        <div class="expert-box" style="margin-top:0.8rem;">
          <strong style="color:#f5c842;">🩺 When to consult an expert</strong><br>
          {remedy.get("when_to_see_expert","Consult an agronomist if symptoms worsen.")}
        </div>
        """)
    else:
        preview_html.append("""
        <div style="color:#999;font-size:0.84rem;padding:1rem 0;">
          No remedy data saved for this scan.
        </div>
        """)

    preview_html.append('</div>')
    st.markdown(''.join(preview_html), unsafe_allow_html=True)
