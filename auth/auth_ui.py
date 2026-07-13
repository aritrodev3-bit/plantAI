"""
auth/auth_ui.py
───────────────
Streamlit authentication UI for PlantAI.

Security features (cumulative — all steps included)
────────────────────────────────────────────────────
  Step 1 — Rate limiting
    • 5 failed attempts / 5 min per-username + per-IP
    • Lockout box shows exact time remaining
    • Signup also rate-limited per-IP

  Step 2 — Input sanitization
    • All fields validated via auth.sanitize before touching the DB
    • XSS-safe: dangerous chars stripped, values HTML-escaped before render
    • Password strength bar (live, updates per keystroke)
    • Generic "Invalid username or password" — no username enumeration

  Step 3 — Session security
    • IP binding: token rejected if client IP changes mid-session
    • Single active session per user: new login revokes all prior tokens
    • Expiry warning: sidebar badge shows time remaining when < 30 min
    • Auto token rotation: fresh 8-hr token issued if < 30 min remain
      and the user is actively using the app

Public API
──────────
  require_auth()  — call once, right after st.set_page_config()
"""

import streamlit as st
from datetime import datetime, timedelta

from auth.database import (
    init_db,
    create_user,
    authenticate_user,
    check_rate_limit,
    record_failed_login,
    clear_rate_limit,
    _recent_attempt_count,
    create_session,
    validate_session,
    rotate_session,
    revoke_session,
    cleanup_expired_sessions,
    get_session_expiry,
    MAX_ATTEMPTS,
    RENEW_WINDOW_MINS,
)
from auth.sanitize import (
    validate_username,
    validate_email,
    validate_password_login,
    validate_password_signup,
    password_strength,
    strip_and_escape,
)

# ── Init DB once per process ──────────────────────────────────────────────────
init_db()

# ── CSS ───────────────────────────────────────────────────────────────────────
_AUTH_CSS = """
<style>
  .auth-logo {
    text-align: center;
    font-size: 2.2rem;
    font-weight: 600;
    letter-spacing: -1px;
    color: #f2f6f3;
    margin-bottom: 0.3rem;
  }
  .auth-logo span { color: #2e7d32; }
  .auth-tagline {
    text-align: center;
    font-size: 0.82rem;
    color: #a6b6ac;
    margin-bottom: 2.2rem;
    letter-spacing: 0.4px;
  }

  /* Input overrides */
  div[data-testid="stTextInput"] input {
    background: #18201b !important;
    border: 1px solid #2b3931 !important;
    border-radius: 10px !important;
    color: #f2f6f3 !important;
    font-size: 0.88rem !important;
    padding-right: 1rem !important;
  }
  div[data-testid="stTextInput"] input:focus {
    border-color: #2e7d32 !important;
    box-shadow: 0 0 0 2px rgba(46, 125, 50, 0.12) !important;
  }
  div[data-testid="stTextInput"] div[data-testid="InputInstructions"] {
    display: none !important;
  }

  /* Primary button */
  div[data-testid="stButton"] > button[kind="primary"] {
    background: #2e7d32 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 0.55rem 1.4rem !important;
    width: 100% !important;
    margin-top: 0.4rem !important;
    transition: opacity 0.15s !important;
  }
  div[data-testid="stButton"] > button[kind="primary"]:hover {
    opacity: 0.88 !important;
  }

  /* Tab styling */
  div[data-testid="stTabs"] button[role="tab"] {
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    color: #666 !important;
  }
  div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: #2e7d32 !important;
    border-bottom-color: #2e7d32 !important;
  }

  .auth-footer {
    text-align: center;
    font-size: 0.72rem;
    color: #87968d;
    margin-top: 2rem;
  }

  /* Lockout warning box */
  .lockout-box {
    background: #2b1718;
    border: 1px solid #6a3437;
    border-left: 3px solid #c62828;
    border-radius: 10px;
    padding: 0.85rem 1rem;
    font-size: 0.83rem;
    color: #c62828;
    margin-bottom: 0.8rem;
    line-height: 1.5;
  }

  /* Password strength bar */
  .strength-wrap  { margin-top: 0.4rem; margin-bottom: 0.2rem; }
  .strength-track {
    background: #243028;
    border-radius: 99px;
    height: 5px;
    overflow: hidden;
  }
  .strength-fill {
    height: 5px;
    border-radius: 99px;
    transition: width 0.3s ease, background 0.3s ease;
  }
  .strength-label { font-size: 0.72rem; margin-top: 0.25rem; font-weight: 500; }
  .strength-hint  { font-size: 0.70rem; color: #a6b6ac; margin-top: 0.15rem; line-height: 1.4; }

  /* User badge in sidebar */
  .user-badge {
    background: #141414;
    border: 1px solid #1f1f1f;
    border-radius: 12px;
    padding: 0.75rem 1rem;
    font-size: 0.82rem;
    color: #aaa;
    margin-bottom: 0.5rem;
  }
  .user-badge strong { color: #5bde8a; }

  /* Session expiry warning in sidebar */
  .expiry-warn {
    background: #2a2a1a;
    border: 1px solid #4a4a1a;
    border-left: 3px solid #f5c842;
    border-radius: 8px;
    padding: 0.55rem 0.85rem;
    font-size: 0.75rem;
    color: #f5c842;
    margin-bottom: 0.5rem;
    line-height: 1.4;
  }
</style>
"""


# ── IP extraction ─────────────────────────────────────────────────────────────

def _get_client_ip() -> str:
    try:
        headers   = st.context.headers
        forwarded = headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return headers.get("Remote-Addr", "127.0.0.1")
    except Exception:
        return "127.0.0.1"


# ── Session state bootstrap ───────────────────────────────────────────────────

def _init_session() -> None:
    defaults = {
        "authenticated":  False,
        "logged_in":      False,
        "user":           None,
        "session_token":  None,
        "signup_success": None,
        "show_login_tab": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ── Password strength bar ─────────────────────────────────────────────────────

def _render_strength_bar(password: str) -> None:
    if not password:
        return
    s = password_strength(password)
    mandatory_missing = [m for m in s["missing"] if "optional" not in m]
    missing_html = ""
    if mandatory_missing:
        missing_html = (
            f'<div class="strength-hint">Needs: {" · ".join(mandatory_missing)}</div>'
        )
    st.markdown(f"""
    <div class="strength-wrap">
      <div class="strength-track">
        <div class="strength-fill"
             style="width:{s['percent']}%; background:{s['color']};"></div>
      </div>
      <div class="strength-label" style="color:{s['color']};">{s['label']}</div>
      {missing_html}
    </div>
    """, unsafe_allow_html=True)


# ── Auth actions ──────────────────────────────────────────────────────────────

def _do_login(username_raw: str, password_raw: str, ip: str) -> None:
    # 1 — Sanitize
    u_check = validate_username(username_raw)
    p_check = validate_password_login(password_raw)
    if not u_check["ok"] or not p_check["ok"]:
        st.error("Invalid username or password.")
        return

    username = u_check["value"]
    password = p_check["value"]

    # 2 — Rate limit
    limit = check_rate_limit(username, ip)
    if limit["blocked"]:
        st.markdown(
            f'<div class="lockout-box">🔒 {limit["reason"]}</div>',
            unsafe_allow_html=True,
        )
        return

    # 3 — Authenticate
    result = authenticate_user(username, password)
    if not result["ok"]:
        record_failed_login(username, ip)
        limit_now = check_rate_limit(username, ip)
        if limit_now["blocked"]:
            st.markdown(
                f'<div class="lockout-box">🔒 {limit_now["reason"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            used = _recent_attempt_count(f"username:{username.lower()}")
            left = max(0, MAX_ATTEMPTS - used)
            warn = (
                f" ({left} attempt{'s' if left != 1 else ''} remaining)"
                if left < MAX_ATTEMPTS else ""
            )
            st.error(f"Invalid username or password.{warn}")
        return

    # 4 — Success: create session (revokes all prior sessions for this user)
    clear_rate_limit(username, ip)
    token = create_session(result["user"]["id"], ip)
    st.session_state["authenticated"] = True
    st.session_state["logged_in"] = True
    st.session_state["user"]          = result["user"]
    st.session_state["session_token"] = token
    st.rerun()


def _do_signup(
    username_raw: str,
    email_raw: str,
    password_raw: str,
    confirm_raw: str,
    ip: str,
) -> None:
    # 1 — Signup rate-limit (per-IP)
    limit = check_rate_limit("__signup__", ip)
    if limit["blocked"]:
        st.markdown(
            f'<div class="lockout-box">🔒 {limit["reason"]}</div>',
            unsafe_allow_html=True,
        )
        return

    # 2 — Validate + sanitize
    u_check = validate_username(username_raw)
    if not u_check["ok"]:
        st.error(u_check["error"])
        return

    e_check = validate_email(email_raw)
    if not e_check["ok"]:
        st.error(e_check["error"])
        return

    p_check = validate_password_signup(password_raw)
    if not p_check["ok"]:
        st.error(p_check["error"])
        return

    if password_raw != confirm_raw:
        st.error("Passwords do not match.")
        record_failed_login("__signup__", ip)
        return

    # 3 — Create user
    result = create_user(u_check["value"], e_check["value"], p_check["value"])
    if result["ok"]:
        st.session_state["signup_success"] = strip_and_escape(u_check["value"])
        st.session_state["show_login_tab"] = True  # auto-switch to Login tab
        st.rerun()
    else:
        record_failed_login("__signup__", ip)
        st.error(result["error"])


# ── Session validation + rotation ─────────────────────────────────────────────

def _validate_and_maybe_rotate(ip: str) -> bool:
    """
    Validate the stored session token against the DB (with IP binding).

    If valid and < RENEW_WINDOW_MINS remain → silently rotate the token
    so the user gets a fresh 8-hr window without re-authenticating.

    Returns True if session is valid, False if expired / revoked / IP mismatch.
    """
    token = st.session_state.get("session_token")
    if not token:
        return False

    # Validate (includes IP binding check)
    user = validate_session(token, ip)
    if user is None:
        # Expired, revoked, or IP mismatch
        st.session_state["authenticated"] = False
        st.session_state["logged_in"] = False
        st.session_state["user"]          = None
        st.session_state["session_token"] = None
        return False

    # Update user data in session state
    st.session_state["logged_in"] = True
    st.session_state["user"] = user

    # ── Token rotation ────────────────────────────────────────────────────────
    expiry = get_session_expiry(token)
    if expiry is not None:
        mins_remaining = (expiry - datetime.utcnow()).total_seconds() / 60
        if 0 < mins_remaining < RENEW_WINDOW_MINS:
            # Silently issue a new token
            new_token = rotate_session(token, user["id"], ip)
            st.session_state["session_token"] = new_token

    return True


# ── Render helpers ────────────────────────────────────────────────────────────

def _render_auth_page(ip: str) -> None:
    st.markdown(_AUTH_CSS, unsafe_allow_html=True)
    st.markdown("""
    <div class="auth-logo">Plant<span>AI</span></div>
    <div class="auth-tagline">Sign in to start diagnosing your plants</div>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2, 1])

    with col:
        # After successful signup, inject JS to auto-click the Login tab
        if st.session_state.get("show_login_tab"):
            st.session_state["show_login_tab"] = False
            st.markdown("""
            <script>
            setTimeout(function() {
                const tabs = window.parent.document.querySelectorAll(
                    '[data-testid="stTabs"] button[role="tab"]'
                );
                if (tabs && tabs[0]) { tabs[0].click(); }
            }, 150);
            </script>
            """, unsafe_allow_html=True)

        login_tab, signup_tab = st.tabs(["🔑  Log In", "🌱  Sign Up"])

        # ── LOGIN TAB ────────────────────────────────────────────────────────
        with login_tab:
            if st.session_state["signup_success"]:
                uname = st.session_state["signup_success"]
                st.success(f"Account created for **{uname}**! Please log in 🌿")
                st.session_state["signup_success"] = None

            st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
            username_li = st.text_input(
                "Username", key="login_username", placeholder="your_username"
            )
            password_li = st.text_input(
                "Password", type="password",
                key="login_password", placeholder="••••••••"
            )
            st.markdown("<div style='height:0.2rem'></div>", unsafe_allow_html=True)
            if st.button("Log In", key="btn_login", type="primary"):
                _do_login(username_li, password_li, ip)

        # ── SIGN-UP TAB ──────────────────────────────────────────────────────
        with signup_tab:
            if st.session_state["signup_success"]:
                uname = st.session_state["signup_success"]
                st.markdown(f'''
                <div style="background:#1a3d28;border:1px solid #2d6b45;border-radius:10px;
                            padding:1rem;text-align:center;margin-bottom:0.8rem;">
                  <div style="color:#5bde8a;font-weight:600;font-size:0.95rem;
                              margin-bottom:0.3rem;">
                    ✅ Account created for <strong>{uname}</strong>!
                  </div>
                  <div style="color:#aaa;font-size:0.82rem;">
                    👆 Click the <strong style="color:#f0f0f0;">Log In</strong>
                    tab above to sign in
                  </div>
                </div>
                ''', unsafe_allow_html=True)
                st.session_state["signup_success"] = None
            else:
                st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
                username_su = st.text_input(
                    "Username", key="signup_username",
                    placeholder="letters, numbers, _ or -"
                )
                email_su = st.text_input(
                    "Email", key="signup_email", placeholder="you@example.com"
                )
                password_su = st.text_input(
                    "Password", type="password", key="signup_password",
                    placeholder="min. 6 chars, 1 uppercase, 1 number"
                )
                _render_strength_bar(password_su)
                confirm_su = st.text_input(
                    "Confirm Password", type="password",
                    key="signup_confirm", placeholder="repeat password"
                )
                st.markdown("<div style='height:0.2rem'></div>", unsafe_allow_html=True)
                if st.button("Create Account", key="btn_signup", type="primary"):
                    _do_signup(username_su, email_su, password_su, confirm_su, ip)

        st.markdown(
            "<div class='auth-footer'>PlantAI · Leaf disease detection</div>",
            unsafe_allow_html=True,
        )


def _render_user_sidebar(ip: str) -> None:
    user  = st.session_state["user"]
    token = st.session_state.get("session_token", "")

    safe_username = strip_and_escape(user["username"])
    safe_email    = strip_and_escape(user["email"])

    # ── Expiry warning ────────────────────────────────────────────────────────
    expiry_html = ""
    expiry = get_session_expiry(token)
    if expiry is not None:
        mins_left = int((expiry - datetime.utcnow()).total_seconds() / 60)
        if 0 < mins_left < RENEW_WINDOW_MINS:
            expiry_html = f"""
            <div class="expiry-warn">
              ⏱ Session renewing soon&nbsp;·&nbsp;{mins_left} min remaining
            </div>"""

    with st.sidebar:
        st.markdown(f"""
        <div class="user-badge">
          👤 Signed in as <strong>{safe_username}</strong><br>
          <span style="font-size:0.72rem;color:#444;">{safe_email}</span>
        </div>
        {expiry_html}
        """, unsafe_allow_html=True)

        if st.button("Log Out", key="btn_logout"):
            revoke_session(token)
            st.session_state["logged_in"] = False
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


# ── Public API ────────────────────────────────────────────────────────────────

def require_auth() -> None:
    """
    Auth gate — call once, right after st.set_page_config() in frontend/app.py.

    Flow
    ────
    Not authenticated          → show login/signup page, st.stop()
    Authenticated, valid token → check IP binding + expiry + auto-rotate
                                  then render sidebar badge, return
    Authenticated, bad token   → force logout, show login page, st.stop()
    """
    _init_session()
    cleanup_expired_sessions()

    ip = _get_client_ip()

    if not st.session_state["authenticated"]:
        st.session_state["logged_in"] = False
        _render_auth_page(ip)
        st.stop()
    else:
        if not _validate_and_maybe_rotate(ip):
            st.warning("⏱ Your session has expired or is no longer valid. Please log in again.")
            _render_auth_page(ip)
            st.stop()
        else:
            _render_user_sidebar(ip)
