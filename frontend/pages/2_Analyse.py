"""
frontend/pages/2_Analyse.py
────────────────────────────
📁 Save as: PLANTDISEASEPROJ/frontend/pages/2_Analyse.py

Full scan flow — migrated exactly from old frontend/app.py.
  1. Upload image
  2. Preview + file info + Analyse button
  3. POST to FastAPI /predict
  4. Show diagnosis cards (condition, status, confidence, inference time, top 5)
  5. GradCAM heatmap (diseased only)
  6. LLM remedy card (diseased only) — with session cache + retry backoff
  7. Healthy card (healthy only)
  8. Auto-save to SQLite via save_scan()
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import io
import json
import time

import requests
import streamlit as st
from PIL import Image

from frontend.db import save_scan
from frontend.runtime import require_login
from frontend.sidebar import render_sidebar
from frontend.ui import inject_shared_styles

# remedy_generator lives in backend/ — imported via sys.path
from backend.remedy_generator import get_remedy

# ── Config ────────────────────────────────────────────────────────────────────
BACKEND_URL = "http://localhost:8000"

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Analyse · PlantAI",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Auth check ────────────────────────────────────────────────────────────────
require_login()

# ── Session cache for remedy results ─────────────────────────────────────────
if "remedy_cache" not in st.session_state:
    st.session_state["remedy_cache"] = {}

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
    max-width: 760px !important;
    margin: 0 auto !important;
}

/* ── Page title ── */
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
    margin-bottom: 2rem;
}

/* ── Upload zone ── */
.upload-zone {
    border: 1.5px dashed #2e2e2e;
    border-radius: 16px;
    padding: 2rem 1.5rem;
    text-align: center;
    background: #141414;
    margin-bottom: 1.5rem;
    transition: border-color 0.2s;
}
.upload-zone:hover { border-color: #5bde8a; }

/* ── Cards ── */
.card {
    background: #141414;
    border: 1px solid #1f1f1f;
    border-radius: 16px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 1rem;
}
.card-label {
    font-size: 0.65rem;
    font-weight: 500;
    letter-spacing: 1.4px;
    text-transform: uppercase;
    color: #555;
    margin-bottom: 0.4rem;
}
.card-value {
    font-size: 1.5rem;
    font-weight: 600;
    color: #f0f0f0;
    line-height: 1.2;
}
.card-value.green  { color: #5bde8a; }
.card-value.yellow { color: #f5c842; }
.card-value.red    { color: #f5665d; }
.card-sub {
    font-family: 'DM Mono', monospace;
    font-size: 0.75rem;
    color: #444;
    margin-top: 0.25rem;
}

/* ── Confidence bar ── */
.bar-wrap {
    background: #1e1e1e;
    border-radius: 99px;
    height: 6px;
    margin-top: 0.8rem;
    overflow: hidden;
}
.bar-fill {
    height: 6px;
    border-radius: 99px;
    background: linear-gradient(90deg, #5bde8a, #30c96e);
}
.bar-fill.yellow { background: linear-gradient(90deg, #f5c842, #e0a800); }
.bar-fill.red    { background: linear-gradient(90deg, #f5665d, #d93b31); }

/* ── Status pill ── */
.pill {
    display: inline-block;
    padding: 0.2rem 0.75rem;
    border-radius: 99px;
    font-size: 0.72rem;
    font-weight: 500;
    letter-spacing: 0.4px;
}
.pill.healthy  { background: #1a3d28; color: #5bde8a; }
.pill.diseased { background: #3d1a1a; color: #f5665d; }
.pill.sev-low    { background: #1a3d28; color: #5bde8a; }
.pill.sev-medium { background: #3d3217; color: #f5c842; }
.pill.sev-high   { background: #3d1a1a; color: #f5665d; }

/* ── Top-5 score rows ── */
.score-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.5rem 0;
    border-bottom: 1px solid #1c1c1c;
}
.score-row:last-child { border-bottom: none; }
.score-name {
    font-size: 0.82rem;
    color: #bbb;
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    padding-right: 1rem;
}
.score-pct {
    font-family: 'DM Mono', monospace;
    font-size: 0.82rem;
    color: #5bde8a;
    min-width: 52px;
    text-align: right;
}
.score-bar-wrap {
    width: 90px;
    background: #1e1e1e;
    border-radius: 99px;
    height: 4px;
    margin: 0 0.8rem;
    overflow: hidden;
}
.score-bar-fill {
    height: 4px;
    border-radius: 99px;
    background: #5bde8a44;
}

/* ── Divider ── */
.divider {
    border: none;
    border-top: 1px solid #1f1f1f;
    margin: 1.5rem 0;
}

/* ── GradCAM ── */
.gradcam-label {
    font-size: 0.65rem;
    font-weight: 500;
    letter-spacing: 1.4px;
    text-transform: uppercase;
    color: #555;
    margin-bottom: 0.5rem;
    text-align: center;
}
.gradcam-caption {
    font-size: 0.72rem;
    color: #444;
    text-align: center;
    margin-top: 0.5rem;
}
.gradcam-wrap {
    background: #141414;
    border: 1px solid #1f1f1f;
    border-radius: 16px;
    padding: 1rem;
    margin-bottom: 1rem;
}

/* ── Remedy card ── */
.remedy-card {
    background: #141414;
    border: 1px solid #1f1f1f;
    border-radius: 16px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 1rem;
}
.remedy-section-title {
    font-size: 0.65rem;
    font-weight: 500;
    letter-spacing: 1.4px;
    text-transform: uppercase;
    color: #555;
    margin-bottom: 0.75rem;
}
.remedy-overview {
    font-size: 0.87rem;
    color: #aaa;
    line-height: 1.65;
}
.remedy-item {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    padding: 0.4rem 0;
    font-size: 0.83rem;
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
    margin-top: 0.38rem;
    flex-shrink: 0;
}
.remedy-dot.yellow { background: #f5c842; }
.remedy-dot.blue   { background: #5bc8de; }
.expert-box {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-left: 3px solid #f5c842;
    border-radius: 10px;
    padding: 0.85rem 1rem;
    font-size: 0.83rem;
    color: #aaa;
    line-height: 1.5;
}

/* ── Healthy card ── */
.healthy-card {
    background: #141414;
    border: 1px solid #1f1f1f;
    border-radius: 16px;
    padding: 2.5rem 2rem;
    text-align: center;
    margin-bottom: 1rem;
}

/* ── Analyse button ── */
div[data-testid="stButton"] > button {
    background: #5bde8a !important;
    color: #0d0d0d !important;
    border: none !important;
    border-radius: 10px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.9rem !important;
    font-weight: 600 !important;
    padding: 0.65rem 2rem !important;
    width: 100% !important;
    transition: opacity 0.15s !important;
    letter-spacing: 0.2px !important;
}
div[data-testid="stButton"] > button:hover {
    opacity: 0.88 !important;
    transform: none !important;
}

img { border-radius: 12px; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
inject_shared_styles("760px")
render_sidebar("analyse")

# ── Helpers (identical to original frontend/app.py) ──────────────────────────

def clean_label(raw: str) -> str:
    parts = raw.split("___")
    if len(parts) == 2:
        plant, condition = parts
        plant     = plant.replace("_", " ").replace(",", "").strip()
        condition = condition.replace("_", " ").strip()
        return f"{condition} ({plant})"
    return raw.replace("_", " ")


def confidence_color(conf: float) -> str:
    if conf >= 80: return "green"
    if conf >= 50: return "yellow"
    return "red"


def is_healthy(label: str) -> bool:
    return "healthy" in label.lower()


def call_backend(image_bytes: bytes, filename: str) -> dict:
    resp = requests.post(
        f"{BACKEND_URL}/predict",
        files={"file": (filename, image_bytes, "image/jpeg")},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def call_gradcam(image_bytes: bytes, filename: str) -> Image.Image | None:
    try:
        resp = requests.post(
            f"{BACKEND_URL}/gradcam",
            files={"file": (filename, image_bytes, "image/jpeg")},
            timeout=30,
        )
        if resp.status_code == 200:
            return Image.open(io.BytesIO(resp.content))
        return None
    except Exception:
        return None


def get_remedy_cached(disease_name: str) -> dict:
    """
    Return remedy dict, using session cache first.
    Retries up to 3 times with exponential backoff on 429 errors.
    """
    cache = st.session_state["remedy_cache"]
    if disease_name in cache:
        return cache[disease_name]

    delays = [1, 2, 4]
    last_error = {}
    for attempt, delay in enumerate(delays):
        try:
            result = get_remedy(disease_name)
            if "error" not in result:
                cache[disease_name] = result
                return result
            # If it's a rate-limit error, wait and retry
            if "429" in str(result.get("error", "")):
                if attempt < len(delays) - 1:
                    time.sleep(delay)
                    continue
            last_error = result
            break
        except Exception as e:
            last_error = {"error": str(e)}
            if attempt < len(delays) - 1:
                time.sleep(delay)

    return last_error


def render_remedy_card(remedy: dict) -> None:
    """Render the LLM-generated remedy guide — identical styling to original app."""
    severity  = remedy.get("severity", "Medium")
    sev_class = {"Low": "sev-low", "Medium": "sev-medium", "High": "sev-high"}.get(severity, "sev-medium")

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    # Header row
    st.markdown(f"""
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;">
      <div class="card-label" style="margin-bottom:0;">🌿 Health Guide & Remedies</div>
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
    col1, col2, col3 = st.columns(3, gap="small")

    with col1:
        items_html = "".join([
            f'<div class="remedy-item"><div class="remedy-dot"></div><div>{item}</div></div>'
            for item in remedy.get("remedies", [])
        ])
        st.markdown(f"""
        <div class="remedy-card" style="height:100%;">
          <div class="remedy-section-title">💊 Remedies</div>
          {items_html or '<div style="color:#333;font-size:0.8rem;">None listed.</div>'}
        </div>
        """, unsafe_allow_html=True)

    with col2:
        items_html = "".join([
            f'<div class="remedy-item"><div class="remedy-dot yellow"></div><div>{item}</div></div>'
            for item in remedy.get("dietary_tips", [])
        ])
        st.markdown(f"""
        <div class="remedy-card" style="height:100%;">
          <div class="remedy-section-title">🌱 Soil & Nutrition</div>
          {items_html or '<div style="color:#333;font-size:0.8rem;">None listed.</div>'}
        </div>
        """, unsafe_allow_html=True)

    with col3:
        items_html = "".join([
            f'<div class="remedy-item"><div class="remedy-dot blue"></div><div>{item}</div></div>'
            for item in remedy.get("lifestyle_steps", [])
        ])
        st.markdown(f"""
        <div class="remedy-card" style="height:100%;">
          <div class="remedy-section-title">🔄 Prevention</div>
          {items_html or '<div style="color:#333;font-size:0.8rem;">None listed.</div>'}
        </div>
        """, unsafe_allow_html=True)

    # Expert box
    st.markdown(f"""
    <div class="expert-box">
      <strong style="color:#f5c842;">🩺 When to consult an expert</strong><br>
      {remedy.get("when_to_see_expert", "Consult an agronomist if symptoms worsen.")}
    </div>
    """, unsafe_allow_html=True)


# ── Page header ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="page-title">Analyse Leaf</div>
<div class="page-sub">Upload a leaf image to run an EfficientNet-B0 diagnosis</div>
""", unsafe_allow_html=True)

# ── Upload ────────────────────────────────────────────────────────────────────
uploaded = st.file_uploader(
    label="Drop a leaf image here",
    type=["jpg", "jpeg", "png", "webp"],
    label_visibility="collapsed",
)

if not uploaded:
    st.markdown("""
    <div class="upload-zone">
      <div style="font-size:2rem;margin-bottom:0.5rem">🌿</div>
      <div style="font-size:0.9rem;color:#555;">Upload a leaf image to begin diagnosis</div>
      <div style="font-size:0.75rem;color:#333;margin-top:0.3rem;">JPG · PNG · WEBP</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── Preview + file info ───────────────────────────────────────────────────────
image = Image.open(uploaded).convert("RGB")

col_img, col_btn = st.columns([3, 2], gap="large")

with col_img:
    st.image(image, width=400)

with col_btn:
    st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)
    st.markdown(f"""
    <div class="card-label">File</div>
    <div style="font-size:0.85rem;color:#aaa;margin-bottom:1rem;
                white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
      {uploaded.name}
    </div>
    <div class="card-label">Dimensions</div>
    <div style="font-size:0.85rem;color:#aaa;margin-bottom:1.2rem;">
      {image.width} × {image.height} px
    </div>
    <div class="card-label">Size</div>
    <div style="font-size:0.85rem;color:#aaa;margin-bottom:1.4rem;">
      {round(uploaded.size / 1024, 1)} KB
    </div>
    """, unsafe_allow_html=True)
    analyse = st.button("Analyse Leaf →")

if not analyse:
    st.stop()

# ════════════════════════════════════════════════════════════════════════════
# ANALYSE FLOW
# ════════════════════════════════════════════════════════════════════════════

# ── Step 1: Run inference ─────────────────────────────────────────────────────
with st.spinner("Running diagnosis..."):
    try:
        img_bytes = io.BytesIO()
        image.save(img_bytes, format="JPEG", quality=95)
        img_bytes = img_bytes.getvalue()

        start   = time.time()
        result  = call_backend(img_bytes, uploaded.name)
        elapsed = round((time.time() - start) * 1000)

        # GradCAM only for diseased plants
        heatmap_img = None
        pred_raw_check = result.get("predicted_class", "")
        if not is_healthy(pred_raw_check):
            heatmap_img = call_gradcam(img_bytes, uploaded.name)

    except requests.exceptions.ConnectionError:
        st.error("⚠️ Cannot reach the backend. Make sure it's running on port 8000.")
        st.stop()
    except Exception as e:
        st.error(f"Something went wrong: {e}")
        st.stop()

pred_raw   = result["predicted_class"]
pred_label = clean_label(pred_raw)
confidence = result["confidence"]
all_scores = result["all_scores"]
conf_color = confidence_color(confidence)
health_tag = "healthy" if is_healthy(pred_raw) else "diseased"

# ── Step 2: Diagnosis cards ───────────────────────────────────────────────────
st.markdown("<hr class='divider'>", unsafe_allow_html=True)
st.markdown("<div class='card-label' style='margin-bottom:0.8rem'>Diagnosis</div>",
            unsafe_allow_html=True)

c1, c2 = st.columns([5, 2], gap="small")
with c1:
    st.markdown(f"""
    <div class="card">
      <div class="card-label">Detected Condition</div>
      <div class="card-value">{pred_label}</div>
      <div class="card-sub">{pred_raw}</div>
    </div>
    """, unsafe_allow_html=True)
with c2:
    st.markdown(f"""
    <div class="card" style="text-align:center;">
      <div class="card-label">Status</div>
      <div style="margin-top:0.7rem;">
        <span class="pill {health_tag}">
          {'✓ Healthy' if health_tag == 'healthy' else '✗ Diseased'}
        </span>
      </div>
    </div>
    """, unsafe_allow_html=True)

c3, c4 = st.columns(2, gap="small")
with c3:
    st.markdown(f"""
    <div class="card">
      <div class="card-label">Confidence</div>
      <div class="card-value {conf_color}">{confidence}%</div>
      <div class="bar-wrap">
        <div class="bar-fill {conf_color}" style="width:{int(confidence)}%"></div>
      </div>
    </div>
    """, unsafe_allow_html=True)
with c4:
    st.markdown(f"""
    <div class="card">
      <div class="card-label">Inference Time</div>
      <div class="card-value">{elapsed}<span style="font-size:1rem;color:#666"> ms</span></div>
      <div class="card-sub">CPU · EfficientNet-B0</div>
    </div>
    """, unsafe_allow_html=True)

# Top-5 predictions
top5      = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)[:5]
max_score = top5[0][1] if top5 else 1
rows_html = ""
for name, pct in top5:
    bar_pct    = int((pct / max_score) * 100) if max_score > 0 else 0
    rows_html += (
        f'<div class="score-row">'
        f'<div class="score-name">{clean_label(name)}</div>'
        f'<div class="score-bar-wrap">'
        f'<div class="score-bar-fill" style="width:{bar_pct}%"></div>'
        f'</div>'
        f'<div class="score-pct">{pct}%</div>'
        f'</div>'
    )
st.markdown(f"""
<div class="card">
  <div class="card-label" style="margin-bottom:0.6rem">Top 5 Predictions</div>
  {rows_html}
</div>
""", unsafe_allow_html=True)

# ── Step 3: GradCAM (diseased only) ──────────────────────────────────────────
if heatmap_img is not None:
    st.markdown("<hr class='divider'>", unsafe_allow_html=True)
    st.markdown("""
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.8rem;">
      <div class="card-label" style="margin-bottom:0;">🔥 GradCAM — Diseased Region Heatmap</div>
    </div>
    """, unsafe_allow_html=True)

    gc1, gc2 = st.columns(2, gap="small")
    with gc1:
        st.markdown('<div class="gradcam-label">Original</div>', unsafe_allow_html=True)
        st.image(image, width=400)
    with gc2:
        st.markdown('<div class="gradcam-label">Heatmap Overlay</div>', unsafe_allow_html=True)
        st.image(heatmap_img, width=400)

    st.markdown("""
    <div class="gradcam-caption">
      🔴 Red / yellow regions = areas the model focused on to make this diagnosis
    </div>
    """, unsafe_allow_html=True)

# ── Step 4: Remedy card OR healthy card ──────────────────────────────────────
remedy = None
severity_val = "Medium"

if not is_healthy(pred_raw):
    with st.spinner("Generating health guide..."):
        remedy = get_remedy_cached(pred_raw)

    if "error" in remedy:
        detail = remedy.get("detail", "")
        msg = remedy["error"]
        if detail:
            msg += f" — {detail}"
        st.warning(f"⚠️ Could not load remedies: {msg}")
        remedy = None
    else:
        severity_val = remedy.get("severity", "Medium")
        render_remedy_card(remedy)
else:
    st.markdown("""
    <div class="healthy-card">
      <div style="font-size:1.6rem;margin-bottom:0.6rem;">✅</div>
      <div style="color:#5bde8a;font-weight:600;font-size:1rem;margin-bottom:0.3rem;">
        Plant looks healthy!
      </div>
      <div style="font-size:0.83rem;color:#555;">
        No disease detected. Keep up the good care.
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── Step 5: Auto-save to SQLite ──────────────────────────────────────────────
# Use a session state flag to ensure save_scan() runs exactly once per scan.
# Without this, Streamlit reruns wipe remedy/img_bytes before the save executes.
_save_key = f"saved_{pred_raw}_{confidence}"
if not st.session_state.get(_save_key):
    try:
        username   = st.session_state["user"]["username"]
        remedy_str = json.dumps(remedy) if remedy else json.dumps({})

        save_scan(
            username=username,
            filename=uploaded.name,
            predicted_class=pred_raw,
            confidence=confidence,
            severity=severity_val,
            remedy_json=remedy_str,
            image_blob=img_bytes,
        )
        st.session_state[_save_key] = True
    except Exception as e:
        # Non-fatal — don't block the user if save fails
        st.caption(f"⚠️ Scan not saved: {e}")
