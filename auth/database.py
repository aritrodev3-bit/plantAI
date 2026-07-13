"""
auth/database.py
────────────────
SQLite database layer for PlantAI authentication.

Tables
──────
  users            — accounts (bcrypt-hashed passwords)
  login_attempts   — per-username + per-IP rate limiting
  sessions         — secure session tokens with expiry + IP binding

Security & concurrency properties (all steps)
──────────────────────────────────────────────
  Step 1 — Rate limiting (per-username + per-IP, 5 attempts / 5 min)
  Step 2 — Sanitized inputs, generic error messages, no enumeration
  Step 3 — IP-bound session tokens, single active session per user,
            8-hr TTL, 30-min auto-rotation
  Step 4 — Connection pool (5 connections, Queue-based, non-blocking
            borrow with timeout), WAL journal mode, write-retry wrapper,
            explicit transactions for all multi-step operations,
            sized for 20 concurrent users
"""

import base64
import hashlib
import hmac
import os
import queue
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

# ── DB path ───────────────────────────────────────────────────────────────────
_AUTH_DIR = Path(__file__).resolve().parent
DB_PATH   = str(_AUTH_DIR / "users.db")

# ── Rate-limit config ─────────────────────────────────────────────────────────
MAX_ATTEMPTS     = 5
LOCKOUT_WINDOW   = 5 * 60      # seconds
LOCKOUT_DURATION = 5 * 60      # seconds

# ── Session config ────────────────────────────────────────────────────────────
SESSION_TTL_HOURS  = 8
RENEW_WINDOW_MINS  = 30

# â”€â”€ Password hashing config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_HASH_NAME = "sha256"
_SALT_BYTES = 16
_PBKDF2_ITERATIONS = 600_000

# ── Connection pool config ────────────────────────────────────────────────────
# WAL mode allows N readers + 1 writer simultaneously.
# For 20 concurrent users: most requests are reads (session validation),
# so 5 pooled connections handles the write queue comfortably.
_POOL_SIZE        = 5
_POOL_TIMEOUT     = 10         # seconds to wait for a free connection
_WRITE_RETRIES    = 5          # retry attempts on "database is locked"
_WRITE_RETRY_WAIT = 0.1        # seconds between retries (doubles each time)


# ── Connection pool ───────────────────────────────────────────────────────────

class _ConnectionPool:
    """
    A simple thread-safe SQLite connection pool backed by a Queue.

    Usage
    -----
        with pool.connection() as conn:
            conn.execute(...)
    """

    def __init__(self, db_path: str, pool_size: int) -> None:
        self._db_path = db_path
        self._pool    = queue.Queue(maxsize=pool_size)
        for _ in range(pool_size):
            self._pool.put(self._make_connection())

    def _make_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # WAL: multiple readers never block each other;
        # a writer only briefly blocks other writers, not readers.
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        # Busy timeout: SQLite will retry internally for up to N ms
        # before raising OperationalError — complements our retry wrapper.
        conn.execute("PRAGMA busy_timeout=3000;")
        return conn

    @contextmanager
    def connection(self):
        """
        Borrow a connection from the pool, yield it, then return it.
        Raises RuntimeError if no connection is available within _POOL_TIMEOUT.
        """
        try:
            conn = self._pool.get(timeout=_POOL_TIMEOUT)
        except queue.Empty:
            raise RuntimeError(
                "Database connection pool exhausted. "
                "Too many simultaneous requests — please try again shortly."
            )
        try:
            yield conn
        except sqlite3.DatabaseError:
            # If the connection is corrupted, replace it with a fresh one
            try:
                conn.close()
            except Exception:
                pass
            conn = self._make_connection()
            raise
        finally:
            self._pool.put(conn)


# Initialise the pool once at module import time (safe — no DB writes yet)
_pool = _ConnectionPool(DB_PATH, _POOL_SIZE)


# ── Write retry wrapper ───────────────────────────────────────────────────────

def _execute_with_retry(fn, *args, **kwargs):
    """
    Call fn(*args, **kwargs) and retry up to _WRITE_RETRIES times if
    SQLite raises OperationalError (database is locked).
    Uses exponential back-off starting at _WRITE_RETRY_WAIT seconds.
    """
    wait     = _WRITE_RETRY_WAIT
    last_exc: Exception = sqlite3.OperationalError("database is locked")
    for attempt in range(_WRITE_RETRIES):
        try:
            return fn(*args, **kwargs)
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower():
                last_exc = exc
                time.sleep(wait)
                wait *= 2          # exponential back-off
            else:
                raise
    raise last_exc


# ── Schema ────────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER  PRIMARY KEY AUTOINCREMENT,
    username      TEXT     NOT NULL UNIQUE COLLATE NOCASE,
    email         TEXT     NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT     NOT NULL,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS login_attempts (
    id           INTEGER  PRIMARY KEY AUTOINCREMENT,
    identifier   TEXT     NOT NULL,
    attempted_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_attempts_identifier
    ON login_attempts (identifier, attempted_at);

CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT     PRIMARY KEY,
    user_id     INTEGER  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at  DATETIME NOT NULL,
    ip_address  TEXT     NOT NULL,
    is_valid    INTEGER  DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_sessions_token
    ON sessions (token, is_valid, expires_at);

CREATE INDEX IF NOT EXISTS idx_sessions_user
    ON sessions (user_id, is_valid);
"""


def init_db() -> None:
    """Create the database file, tables, and indexes if they don't exist."""
    os.makedirs(_AUTH_DIR, exist_ok=True)
    def _init(conn):
        for statement in _SCHEMA.strip().split(";"):
            s = statement.strip()
            if s:
                conn.execute(s)
        conn.commit()
    with _pool.connection() as conn:
        _execute_with_retry(_init, conn)


# ── Password helpers ──────────────────────────────────────────────────────────

def _hash_password(plain: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        _HASH_NAME,
        plain.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
    )
    salt_b64 = base64.b64encode(salt).decode("ascii")
    hash_b64 = base64.b64encode(derived).decode("ascii")
    return f"pbkdf2_{_HASH_NAME}${_PBKDF2_ITERATIONS}${salt_b64}${hash_b64}"


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        scheme, iterations, salt_b64, hash_b64 = hashed.split("$", maxsplit=3)
        if scheme != f"pbkdf2_{_HASH_NAME}":
            return False
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(hash_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac(
            _HASH_NAME,
            plain.encode("utf-8"),
            salt,
            int(iterations),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


# ── Rate limiting ─────────────────────────────────────────────────────────────

def _record_failed_attempt(conn: sqlite3.Connection, identifier: str) -> None:
    conn.execute(
        "INSERT INTO login_attempts (identifier) VALUES (?)", (identifier,)
    )


def _clear_attempts(conn: sqlite3.Connection, identifier: str) -> None:
    conn.execute(
        "DELETE FROM login_attempts WHERE identifier = ?", (identifier,)
    )


def _recent_attempt_count(identifier: str) -> int:
    cutoff = datetime.utcnow() - timedelta(seconds=LOCKOUT_WINDOW)
    with _pool.connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM login_attempts "
            "WHERE identifier = ? AND attempted_at >= ?",
            (identifier, cutoff.isoformat()),
        ).fetchone()
    return row["cnt"] if row else 0


def _lockout_seconds_remaining(identifier: str) -> int:
    cutoff = datetime.utcnow() - timedelta(seconds=LOCKOUT_WINDOW)
    with _pool.connection() as conn:
        rows = conn.execute(
            "SELECT attempted_at FROM login_attempts "
            "WHERE identifier = ? AND attempted_at >= ? "
            "ORDER BY attempted_at ASC",
            (identifier, cutoff.isoformat()),
        ).fetchall()

    if len(rows) < MAX_ATTEMPTS:
        return 0

    nth_time    = datetime.fromisoformat(rows[MAX_ATTEMPTS - 1]["attempted_at"])
    unlock_time = nth_time + timedelta(seconds=LOCKOUT_DURATION)
    remaining   = (unlock_time - datetime.utcnow()).total_seconds()
    return max(0, int(remaining))


def check_rate_limit(username: str, ip: str) -> dict:
    """
    Returns {"blocked": False}
         or {"blocked": True, "seconds": int, "reason": str}.
    """
    for identifier in (f"username:{username.lower()}", f"ip:{ip}"):
        secs = _lockout_seconds_remaining(identifier)
        if secs > 0:
            mins   = secs // 60
            secs_r = secs % 60
            tstr   = f"{mins}m {secs_r}s" if mins else f"{secs_r}s"
            return {
                "blocked": True,
                "seconds": secs,
                "reason":  f"Too many failed attempts. Try again in **{tstr}**.",
            }
    return {"blocked": False}


def record_failed_login(username: str, ip: str) -> None:
    """Record failed login — both username and IP buckets, in one transaction."""
    def _write(conn):
        _record_failed_attempt(conn, f"username:{username.lower()}")
        _record_failed_attempt(conn, f"ip:{ip}")
        conn.commit()
    with _pool.connection() as conn:
        _execute_with_retry(_write, conn)


def clear_rate_limit(username: str, ip: str) -> None:
    """Clear rate-limit counters on successful login, in one transaction."""
    def _write(conn):
        _clear_attempts(conn, f"username:{username.lower()}")
        _clear_attempts(conn, f"ip:{ip}")
        conn.commit()
    with _pool.connection() as conn:
        _execute_with_retry(_write, conn)


# ── Session management ────────────────────────────────────────────────────────

def revoke_all_user_sessions(user_id: int) -> None:
    """
    Revoke every active session for this user.
    Called before creating a new one — enforces single active session.
    """
    def _write(conn):
        conn.execute(
            "UPDATE sessions SET is_valid = 0 "
            "WHERE user_id = ? AND is_valid = 1",
            (user_id,),
        )
        conn.commit()
    with _pool.connection() as conn:
        _execute_with_retry(_write, conn)


def create_session(user_id: int, ip: str) -> str:
    """
    Revoke all prior sessions for this user, then atomically create a new one.
    Returns the new token string.
    """
    token      = secrets.token_urlsafe(48)
    expires_at = datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)

    def _write(conn):
        # Revoke all prior sessions + insert new one in a single transaction
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE sessions SET is_valid = 0 "
            "WHERE user_id = ? AND is_valid = 1",
            (user_id,),
        )
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at, ip_address) "
            "VALUES (?,?,?,?)",
            (token, user_id, expires_at.isoformat(), ip),
        )
        conn.execute("COMMIT")

    with _pool.connection() as conn:
        _execute_with_retry(_write, conn)

    return token


def validate_session(token: str, ip: str) -> dict | None:
    """
    Validate a session token.

    Checks
    ──────
    1. Token exists and is_valid = 1
    2. Not expired
    3. IP matches the one the token was issued to (binding)

    Returns user dict on success, None on any failure.
    """
    if not token:
        return None

    with _pool.connection() as conn:
        row = conn.execute(
            """
            SELECT s.user_id, s.expires_at, s.is_valid, s.ip_address,
                   u.username, u.email
            FROM   sessions s
            JOIN   users    u ON u.id = s.user_id
            WHERE  s.token = ?
            """,
            (token,),
        ).fetchone()

    if row is None or not row["is_valid"]:
        return None

    # ── IP binding ────────────────────────────────────────────────────────────
    local_ips = {"127.0.0.1", "::1", "localhost"}
    stored_ip = row["ip_address"]
    if stored_ip not in local_ips and ip not in local_ips:
        if stored_ip != ip:
            # Revoke immediately — possible session hijack attempt
            def _revoke(conn):
                conn.execute(
                    "UPDATE sessions SET is_valid = 0 WHERE token = ?", (token,)
                )
                conn.commit()
            with _pool.connection() as conn:
                _execute_with_retry(_revoke, conn)
            return None

    # ── Expiry ────────────────────────────────────────────────────────────────
    if datetime.utcnow() > datetime.fromisoformat(row["expires_at"]):
        def _expire(conn):
            conn.execute(
                "UPDATE sessions SET is_valid = 0 WHERE token = ?", (token,)
            )
            conn.commit()
        with _pool.connection() as conn:
            _execute_with_retry(_expire, conn)
        return None

    return {
        "id":         row["user_id"],
        "username":   row["username"],
        "email":      row["email"],
        "expires_at": row["expires_at"],
    }


def get_session_expiry(token: str) -> datetime | None:
    """Return the expiry datetime for a valid token, or None."""
    if not token:
        return None
    with _pool.connection() as conn:
        row = conn.execute(
            "SELECT expires_at FROM sessions WHERE token = ? AND is_valid = 1",
            (token,),
        ).fetchone()
    if row is None:
        return None
    return datetime.fromisoformat(row["expires_at"])


def rotate_session(old_token: str, user_id: int, ip: str) -> str:
    """
    Atomically revoke old_token and issue a fresh one with a new 8-hr TTL.
    Both operations happen inside BEGIN IMMEDIATE so no concurrent request
    can observe a gap between revoke and insert.
    """
    new_token  = secrets.token_urlsafe(48)
    expires_at = datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)

    def _write(conn):
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE sessions SET is_valid = 0 WHERE token = ?", (old_token,)
        )
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at, ip_address) "
            "VALUES (?,?,?,?)",
            (new_token, user_id, expires_at.isoformat(), ip),
        )
        conn.execute("COMMIT")

    with _pool.connection() as conn:
        _execute_with_retry(_write, conn)

    return new_token


def revoke_session(token: str) -> None:
    """Revoke a single session token (logout)."""
    if not token:
        return
    def _write(conn):
        conn.execute(
            "UPDATE sessions SET is_valid = 0 WHERE token = ?", (token,)
        )
        conn.commit()
    with _pool.connection() as conn:
        _execute_with_retry(_write, conn)


def cleanup_expired_sessions() -> None:
    """Delete expired and revoked rows — called on every page load."""
    def _write(conn):
        conn.execute(
            "DELETE FROM sessions WHERE is_valid = 0 OR expires_at < ?",
            (datetime.utcnow().isoformat(),),
        )
        conn.commit()
    with _pool.connection() as conn:
        _execute_with_retry(_write, conn)


# ── User management ───────────────────────────────────────────────────────────

def create_user(username: str, email: str, password: str) -> dict:
    """
    Insert a new user. Inputs must already be validated by auth.sanitize.

    Returns
    -------
    {"ok": True,  "user_id": int}
    {"ok": False, "error":   str}
    """
    hashed = _hash_password(password)

    def _write(conn):
        cur = conn.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?,?,?)",
            (username, email, hashed),
        )
        conn.commit()
        return cur.lastrowid

    try:
        with _pool.connection() as conn:
            user_id = _execute_with_retry(_write, conn)
        return {"ok": True, "user_id": user_id}
    except sqlite3.IntegrityError as exc:
        msg = str(exc).lower()
        if "username" in msg:
            return {"ok": False, "error": "That username is already taken."}
        if "email" in msg:
            return {"ok": False, "error": "An account with that email already exists."}
        return {"ok": False, "error": "Sign-up failed. Please try again."}
    except RuntimeError as exc:
        # Pool exhausted
        return {"ok": False, "error": str(exc)}
    except Exception:
        return {"ok": False, "error": "An unexpected error occurred. Please try again."}


def authenticate_user(username: str, password: str) -> dict:
    """
    Verify credentials. Generic error prevents username enumeration.

    Returns
    -------
    {"ok": True,  "user": {"id", "username", "email"}}
    {"ok": False, "error": str}
    """
    try:
        with _pool.connection() as conn:
            row = conn.execute(
                "SELECT id, username, email, password_hash "
                "FROM users WHERE username = ?",
                (username.strip(),),
            ).fetchone()
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception:
        return {"ok": False, "error": "An unexpected error occurred. Please try again."}

    # Deliberately generic — no username enumeration
    if row is None or not _verify_password(password, row["password_hash"]):
        return {"ok": False, "error": "Invalid username or password."}

    return {
        "ok": True,
        "user": {
            "id":       row["id"],
            "username": row["username"],
            "email":    row["email"],
        },
    }


def get_user_by_id(user_id: int) -> dict | None:
    try:
        with _pool.connection() as conn:
            row = conn.execute(
                "SELECT id, username, email FROM users WHERE id = ?", (user_id,)
            ).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    return {"id": row["id"], "username": row["username"], "email": row["email"]}
