from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st


def ensure_project_root(current_file: str) -> Path:
    """Add the project root to ``sys.path`` once and return it."""
    file_path = Path(current_file).resolve()

    for candidate in (file_path.parent, *file_path.parents):
        if (candidate / "frontend").exists() and (candidate / "backend").exists():
            root = candidate
            break
    else:
        root = file_path.parent

    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


def init_session_state() -> None:
    defaults = {
        "authenticated": False,
        "logged_in": False,
        "user": None,
        "session_token": None,
        "signup_success": None,
        "active_page": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_auth_state() -> None:
    st.session_state["authenticated"] = False
    st.session_state["logged_in"] = False
    st.session_state["user"] = None
    st.session_state["session_token"] = None


def require_login() -> None:
    init_session_state()
    if not st.session_state["authenticated"] or not st.session_state["logged_in"]:
        st.switch_page("app.py")
        st.stop()
