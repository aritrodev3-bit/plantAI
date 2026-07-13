"""
auth/sanitize.py
────────────────
Input sanitization and validation for PlantAI auth.

All user-supplied strings pass through this module before
touching the database or being rendered in the UI.

Rules
─────
  username  — 3–32 chars, alphanumeric + _ and - only, no leading/trailing -_
  email     — basic RFC-5321 structure, max 254 chars
  password  — 6–128 chars, must contain ≥1 uppercase + ≥1 digit (signup only)
"""

import re
import html

# ── Compiled patterns ─────────────────────────────────────────────────────────

# Allows a-z A-Z 0-9 _ -  but not at start or end
_USERNAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_\-]{1,30}[a-zA-Z0-9]$|^[a-zA-Z0-9]{1,2}$')

# Minimal but reliable email pattern
_EMAIL_RE = re.compile(
    r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
)

# XSS / injection character sets to strip from free-text fields
_DANGEROUS_RE = re.compile(r'[<>{}\[\]\'";\\]')


# ── Generic helpers ───────────────────────────────────────────────────────────

def strip_and_escape(value: str, max_length: int = 256) -> str:
    """
    Strip whitespace, truncate to max_length, and HTML-escape dangerous chars.
    Use for any field that might be rendered back into the UI.
    """
    value = value.strip()[:max_length]
    return html.escape(value, quote=True)


def remove_dangerous_chars(value: str) -> str:
    """Remove characters commonly used in XSS / SQL injection attempts."""
    return _DANGEROUS_RE.sub("", value)


# ── Field validators ──────────────────────────────────────────────────────────

def validate_username(raw: str) -> dict:
    """
    Validate and sanitize a username.

    Returns
    -------
    {"ok": True,  "value": str}        — cleaned username
    {"ok": False, "error": str}        — human-readable reason
    """
    cleaned = raw.strip()

    if not cleaned:
        return {"ok": False, "error": "Username is required."}
    if len(cleaned) < 3:
        return {"ok": False, "error": "Username must be at least 3 characters."}
    if len(cleaned) > 32:
        return {"ok": False, "error": "Username must be 32 characters or fewer."}
    if not _USERNAME_RE.match(cleaned):
        return {
            "ok": False,
            "error": (
                "Username may only contain letters, numbers, hyphens, and "
                "underscores, and must not start or end with a hyphen or underscore."
            ),
        }
    # Final escape — should be a no-op for valid usernames, but belt-and-braces
    return {"ok": True, "value": remove_dangerous_chars(cleaned)}


def validate_email(raw: str) -> dict:
    """
    Validate and sanitize an email address.

    Returns
    -------
    {"ok": True,  "value": str}
    {"ok": False, "error": str}
    """
    cleaned = raw.strip().lower()

    if not cleaned:
        return {"ok": False, "error": "Email is required."}
    if len(cleaned) > 254:
        return {"ok": False, "error": "Email address is too long."}
    if not _EMAIL_RE.match(cleaned):
        return {"ok": False, "error": "Please enter a valid email address."}

    return {"ok": True, "value": cleaned}


def validate_password_login(raw: str) -> dict:
    """
    Minimal password check for the login form — only verifies it was provided.
    (Full strength check is only applied at signup time.)

    Returns
    -------
    {"ok": True,  "value": str}
    {"ok": False, "error": str}
    """
    if not raw:
        return {"ok": False, "error": "Password is required."}
    if len(raw) > 128:
        return {"ok": False, "error": "Password is too long."}
    return {"ok": True, "value": raw}


def validate_password_signup(raw: str) -> dict:
    """
    Full password strength check for the signup form.
    Rules: 6–128 chars, ≥1 uppercase letter, ≥1 digit.

    Returns
    -------
    {"ok": True,  "value": str}
    {"ok": False, "error": str}
    """
    if not raw:
        return {"ok": False, "error": "Password is required."}
    if len(raw) < 6:
        return {"ok": False, "error": "Password must be at least 6 characters."}
    if len(raw) > 128:
        return {"ok": False, "error": "Password must be 128 characters or fewer."}
    if not any(c.isupper() for c in raw):
        return {"ok": False, "error": "Password must contain at least one uppercase letter."}
    if not any(c.isdigit() for c in raw):
        return {"ok": False, "error": "Password must contain at least one number."}
    return {"ok": True, "value": raw}


# ── Password strength scorer (for the UI strength bar) ────────────────────────

def password_strength(raw: str) -> dict:
    """
    Score a password from 0–4 and return a label + color for the strength bar.

    Scoring criteria (1 point each):
      1. Length ≥ 8
      2. Contains an uppercase letter
      3. Contains a digit
      4. Contains a special character

    Returns
    -------
    {
        "score":   int,     # 0–4
        "label":   str,     # "Weak" | "Fair" | "Good" | "Strong"
        "color":   str,     # CSS hex color
        "percent": int,     # 0–100 for the bar width
        "missing": list[str]  # list of unmet requirements
    }
    """
    score   = 0
    missing = []

    if len(raw) >= 8:
        score += 1
    else:
        missing.append("at least 8 characters")

    if any(c.isupper() for c in raw):
        score += 1
    else:
        missing.append("an uppercase letter")

    if any(c.isdigit() for c in raw):
        score += 1
    else:
        missing.append("a number")

    if any(c in r'!@#$%^&*()_+-=[]{}|;:,.<>?' for c in raw):
        score += 1
    else:
        missing.append("a special character (optional)")

    labels   = ["Very Weak", "Weak", "Fair", "Good", "Strong"]
    colors   = ["#f5665d",   "#f5665d", "#f5c842", "#5bde8a", "#5bde8a"]
    percents = [10,           30,        55,         80,        100]

    return {
        "score":   score,
        "label":   labels[score],
        "color":   colors[score],
        "percent": percents[score],
        "missing": missing,
    }