"""
frontend/db.py
──────────────
SQLite helper for PlantAI scan history.

Functions
─────────
  init_db()
  save_scan(username, filename, predicted_class,
            confidence, severity, remedy_json, image_blob)
  get_scans(username)          → list[dict]  — cached 60s
  get_scan_by_id(scan_id)      → dict | None
  delete_scan(scan_id)
  get_stats(username)          → dict         — cached 60s

Image compression
─────────────────
  PIL resize max 400×400, JPEG quality 75 before INSERT.

Run location
────────────
  Intended to be imported by pages/ running from inside frontend/.
  scans.db is created in the same directory as this file.
"""

import sqlite3
import json
import io
import os
from datetime import datetime, timedelta
from collections import Counter

import streamlit as st
from PIL import Image

# ── DB path — sits next to this file (frontend/scans.db) ─────────────────────
_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scans.db")


# ── Schema ────────────────────────────────────────────────────────────────────
_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS scans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT,
    username        TEXT,
    filename        TEXT,
    predicted_class TEXT,
    confidence      REAL,
    severity        TEXT,
    remedy_json     TEXT,
    image_blob      BLOB
);
"""


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    """Return a connection with row_factory set to Row for dict-like access."""
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _compress_image(image_bytes: bytes) -> bytes:
    """
    Resize image to fit within 400×400 (preserving aspect ratio)
    and re-encode as JPEG at quality 75.
    Returns compressed bytes.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img.thumbnail((400, 400), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75, optimize=True)
        return buf.getvalue()
    except Exception:
        # If anything goes wrong, store original bytes rather than crash
        return image_bytes


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row)


def _clean_label(raw: str) -> str:
    """
    Convert raw PlantVillage class name to a human-readable label.
    e.g. 'Tomato___Early_blight' → 'Early blight (Tomato)'
    """
    parts = raw.split("___")
    if len(parts) == 2:
        plant, condition = parts
        plant     = plant.replace("_", " ").replace(",", "").strip()
        condition = condition.replace("_", " ").strip()
        return f"{condition} ({plant})"
    return raw.replace("_", " ")


# ── Public API ────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create the scans table if it does not already exist."""
    with _get_conn() as conn:
        conn.execute(_CREATE_TABLE)
        conn.commit()


def save_scan(
    username:        str,
    filename:        str,
    predicted_class: str,
    confidence:      float,
    severity:        str,
    remedy_json:     str,
    image_blob:      bytes,
) -> int:
    """
    Insert a new scan row and return the new row id.

    image_blob is compressed (max 400×400, JPEG q75) before storage.
    remedy_json should be a JSON-encoded string (json.dumps(remedy_dict)).
    """
    compressed = _compress_image(image_blob)
    timestamp  = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    with _get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO scans
              (timestamp, username, filename, predicted_class,
               confidence, severity, remedy_json, image_blob)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (timestamp, username, filename, predicted_class,
             confidence, severity, remedy_json, compressed),
        )
        conn.commit()
        # Clear caches so next read reflects this new row immediately
        get_scans.clear()
        get_stats.clear()
        return int(cursor.lastrowid or 0)


@st.cache_data(ttl=60)
def get_scans(username: str) -> list[dict]:
    """
    Return all scans for a user as a list of dicts, ordered by timestamp DESC.
    Cached for 60 seconds.
    """
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM scans WHERE username = ? ORDER BY timestamp DESC",
            (username,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_scan_by_id(scan_id: int) -> dict | None:
    """Return a single scan dict, or None if not found."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM scans WHERE id = ?", (scan_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def delete_scan(scan_id: int) -> None:
    """Delete a scan by id and invalidate caches."""
    with _get_conn() as conn:
        conn.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
        conn.commit()
    get_scans.clear()
    get_stats.clear()


def delete_all_scans(username: str) -> None:
    """Delete every scan for a user (used in Profile danger zone)."""
    with _get_conn() as conn:
        conn.execute("DELETE FROM scans WHERE username = ?", (username,))
        conn.commit()
    get_scans.clear()
    get_stats.clear()


@st.cache_data(ttl=60)
def get_stats(username: str) -> dict:
    """
    Return aggregate stats for a user.

    Keys
    ────
      total_scans         int
      unique_diseases     int
      avg_confidence      float  (1 decimal place)
      healthy_rate        float  percentage (1 decimal place)
      most_common_disease str    (clean label, or 'None yet')
      scans_per_day       dict   {date_str: count} last 7 days
      top_diseases        list   [{name, count, percentage}] top 5

    Cached for 60 seconds.
    """
    scans = get_scans(username)  # already cached

    # ── Defaults for empty history ─────────────────────────────────────────────
    if not scans:
        today = datetime.utcnow().date()
        return {
            "total_scans":         0,
            "unique_diseases":     0,
            "avg_confidence":      0.0,
            "healthy_rate":        0.0,
            "most_common_disease": "None yet",
            "scans_per_day":       {
                str(today - timedelta(days=i)): 0 for i in range(6, -1, -1)
            },
            "top_diseases":        [],
        }

    # ── Core counts ───────────────────────────────────────────────────────────
    total      = len(scans)
    classes    = [s["predicted_class"] for s in scans]
    confidences = [s["confidence"] for s in scans]

    healthy_count  = sum(1 for c in classes if "healthy" in c.lower())
    
    unique_diseases = len(set(
        c for c in classes if "healthy" not in c.lower()
    ))

    avg_conf     = round(sum(confidences) / total, 1) if total else 0.0
    healthy_rate = round((healthy_count / total) * 100, 1) if total else 0.0

    # ── Most common disease (excluding healthy) ────────────────────────────────
    disease_classes = [c for c in classes if "healthy" not in c.lower()]
    if disease_classes:
        most_common_raw  = Counter(disease_classes).most_common(1)[0][0]
        most_common_disp = _clean_label(most_common_raw)
    else:
        most_common_disp = "None detected"

    # ── Scans per day — last 7 days ────────────────────────────────────────────
    today = datetime.utcnow().date()
    day_labels = [str(today - timedelta(days=i)) for i in range(6, -1, -1)]
    scans_per_day: dict[str, int] = {d: 0 for d in day_labels}

    for s in scans:
        try:
            scan_date = s["timestamp"][:10]  # 'YYYY-MM-DD'
            if scan_date in scans_per_day:
                scans_per_day[scan_date] += 1
        except (TypeError, IndexError):
            pass

    # ── Top 5 diseases (excluding healthy) ────────────────────────────────────
    disease_counter = Counter(disease_classes)
    total_diseased  = sum(disease_counter.values()) or 1  # avoid div/0

    top_diseases = [
        {
            "name":       _clean_label(cls),
            "raw":        cls,
            "count":      cnt,
            "percentage": round((cnt / total_diseased) * 100, 1),
        }
        for cls, cnt in disease_counter.most_common(5)
    ]

    return {
        "total_scans":         total,
        "unique_diseases":     unique_diseases,
        "avg_confidence":      avg_conf,
        "healthy_rate":        healthy_rate,
        "most_common_disease": most_common_disp,
        "scans_per_day":       scans_per_day,
        "top_diseases":        top_diseases,
    }