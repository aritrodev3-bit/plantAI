from __future__ import annotations

import streamlit as st


def inject_shared_styles(max_width: str = "1200px") -> None:
    st.markdown(
        f"""
<style>
:root {{
    --plant-bg: #0f1511;
    --plant-surface: #18201b;
    --plant-surface-soft: #1d2721;
    --plant-border: #2b3931;
    --plant-text: #f2f6f3;
    --plant-muted: #a6b6ac;
    --plant-soft-text: #87968d;
    --plant-accent: #2e7d32;
    --plant-accent-soft: rgba(46, 125, 50, 0.18);
    --plant-danger-soft: #2b1718;
}}

html, body, [class*="css"], .stApp {{
    font-family: 'DM Sans', sans-serif !important;
    background-color: var(--plant-bg) !important;
    color: var(--plant-text) !important;
}}

#MainMenu, footer, header {{
    visibility: hidden;
}}

.main .block-container {{
    padding-top: 2rem !important;
    padding-bottom: 3rem !important;
    max-width: {max_width} !important;
}}

.page-title, .dash-title, .diag-value, .card-value, .stat-value,
.avatar-name, .scan-disease, .score-name, .remedy-overview,
.remedy-item, .expert-box, .danger-desc, .empty-msg, .footer-count,
.diag-sub, .card-sub, .stat-sub, .page-sub, .dash-sub, .scan-ts,
.tbl-header, .avatar-scan-count, .sb-user-label, .sb-username {{
    color: var(--plant-text) !important;
}}

.page-sub, .dash-sub, .diag-sub, .card-sub, .stat-sub, .scan-ts,
.footer-count, .avatar-scan-count, .danger-desc, .empty-msg,
.diag-label, .card-label, .chart-title, .section-title, .panel-label,
.panel-label, .remedy-section-title, .stat-label, .tbl-header,
.gradcam-caption, .gradcam-label, .sb-user-label {{
    color: var(--plant-muted) !important;
}}

.stat-card, .chart-card, .card, .panel-card, .diag-card, .remedy-card,
.filter-bar, .scan-card, .danger-card, .avatar-card, .healthy-card,
.upload-zone, .empty-state, .scan-row, .gradcam-wrap, .remedy-expand {{
    background: var(--plant-surface) !important;
    border: 1px solid var(--plant-border) !important;
    box-shadow: 0 14px 28px rgba(0, 0, 0, 0.18);
}}

.remedy-expand, .diag-card, .remedy-card {{
    background: var(--plant-surface-soft) !important;
}}

.danger-card {{
    background: var(--plant-danger-soft) !important;
}}

.expert-box {{
    background: #2c2614 !important;
    border-color: #72623a !important;
}}

.upload-zone:hover {{
    border-color: var(--plant-accent) !important;
}}

div[data-testid="stTextInput"] input,
div[data-testid="stSelectbox"] > div,
div[data-testid="stDateInput"] input {{
    background: var(--plant-surface) !important;
    border: 1px solid var(--plant-border) !important;
    color: var(--plant-text) !important;
}}

div[data-testid="stTextInput"] input:focus,
div[data-testid="stSelectbox"] > div:focus-within,
div[data-testid="stDateInput"] input:focus {{
    border-color: var(--plant-accent) !important;
    box-shadow: 0 0 0 2px rgba(46, 125, 50, 0.12) !important;
}}

div[data-testid="stButton"] > button,
div[data-testid="stDownloadButton"] > button {{
    border-radius: 10px !important;
    transform: none !important;
}}

div[data-testid="stButton"] > button:hover,
div[data-testid="stDownloadButton"] > button:hover {{
    transform: none !important;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def format_timestamp(raw_ts: str) -> str:
    from datetime import datetime, timezone

    try:
        dt = datetime.strptime(raw_ts, "%Y-%m-%d %H:%M:%S")
        dt = dt.replace(tzinfo=timezone.utc).astimezone()
    except ValueError:
        return raw_ts

    hour = dt.strftime("%I").lstrip("0") or "0"
    return f"{dt.strftime('%b')} {dt.day}, {dt.year} · {hour}:{dt.strftime('%M %p')}"
