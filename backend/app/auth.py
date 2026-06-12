"""Authentication and user management.

Provides JWT-based authentication with password hashing.
Users can register, login, and access protected API routes.
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", secrets.token_hex(32))
TOKEN_EXPIRY_SECONDS = int(os.environ.get("JWT_EXPIRY_SECONDS", "86400"))  # 24h default
DB_PATH = os.environ.get("TRACES_DB_PATH", "traces.db")


# ── Password Hashing (using hashlib PBKDF2 – no extra deps) ──


def _hash_password(password: str, salt: Optional[str] = None) -> tuple:
    """Hash a password using PBKDF2-HMAC-SHA256. Returns (hash_hex, salt_hex)."""
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return dk.hex(), salt


def _verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verify a password against a stored hash."""
    computed, _ = _hash_password(password, salt)
    return hmac.compare_digest(computed, stored_hash)


# ── JWT (minimal implementation – no external dependency) ─


def _base64url_encode(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _base64url_decode(s: str) -> bytes:
    import base64
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def create_token(user_id: str, extra: Optional[Dict[str, Any]] = None) -> str:
    """Create a JWT token for a user."""
    header = _base64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload_data = {
        "sub": user_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_EXPIRY_SECONDS,
    }
    if extra:
        payload_data.update(extra)
    payload = _base64url_encode(json.dumps(payload_data).encode())

    signing_input = f"{header}.{payload}"
    signature = hmac.new(SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256).digest()
    sig = _base64url_encode(signature)

    return f"{header}.{payload}.{sig}"


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode a JWT token. Returns payload dict or None."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b64, payload_b64, sig_b64 = parts

        # Verify signature
        signing_input = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256).digest()
        actual_sig = _base64url_decode(sig_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        # Decode payload
        payload = json.loads(_base64url_decode(payload_b64))

        # Check expiry
        if payload.get("exp", 0) < time.time():
            return None

        return payload
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        return None


# ── Database Schema ──────────────────────────────────────


def _ensure_users_table():
    """Create the users table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                display_name TEXT,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")

        # API keys table for programmatic access
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                key_hash TEXT NOT NULL,
                key_prefix TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash)")

        conn.commit()
    finally:
        conn.close()


# ── User CRUD ────────────────────────────────────────────


def register_user(username: str, password: str, email: Optional[str] = None, display_name: Optional[str] = None) -> Dict[str, Any]:
    """Register a new user. Returns user info dict."""
    _ensure_users_table()
    user_id = secrets.token_hex(16)
    pw_hash, pw_salt = _hash_password(password)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(
            """
            INSERT INTO users (user_id, username, email, password_hash, password_salt, display_name, role)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, username, email, pw_hash, pw_salt, display_name or username, "user"),
        )
        conn.commit()
        return {
            "user_id": user_id,
            "username": username,
            "email": email,
            "display_name": display_name or username,
            "role": "user",
        }
    except sqlite3.IntegrityError as e:
        if "username" in str(e):
            raise ValueError("Username already exists")
        elif "email" in str(e):
            raise ValueError("Email already exists")
        raise
    finally:
        conn.close()


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate a user by username and password. Returns user dict with token or None."""
    _ensure_users_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if not row:
            return None

        if not _verify_password(password, row["password_hash"], row["password_salt"]):
            return None

        # Update last login
        conn.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = ?",
            (row["user_id"],),
        )
        conn.commit()

        token = create_token(row["user_id"], extra={"username": row["username"], "role": row["role"]})

        return {
            "user_id": row["user_id"],
            "username": row["username"],
            "email": row["email"],
            "display_name": row["display_name"],
            "role": row["role"],
            "token": token,
        }
    finally:
        conn.close()


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Get a user by ID."""
    _ensure_users_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT user_id, username, email, display_name, role, created_at, last_login FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_users(limit: int = 50, offset: int = 0) -> list:
    """List all users (admin only)."""
    _ensure_users_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT user_id, username, email, display_name, role, created_at, last_login FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── API Keys ─────────────────────────────────────────────


def create_api_key(user_id: str, name: str) -> Dict[str, Any]:
    """Create an API key for a user. Returns the raw key (shown only once)."""
    _ensure_users_table()
    raw_key = f"atk_{secrets.token_hex(24)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_id = secrets.token_hex(8)
    key_prefix = raw_key[:12] + "..."

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO api_keys (key_id, user_id, key_hash, key_prefix, name) VALUES (?, ?, ?, ?, ?)",
            (key_id, user_id, key_hash, key_prefix, name),
        )
        conn.commit()
        return {
            "key_id": key_id,
            "key": raw_key,
            "key_prefix": key_prefix,
            "name": name,
        }
    finally:
        conn.close()


def verify_api_key(raw_key: str) -> Optional[Dict[str, Any]]:
    """Verify an API key and return the associated user info."""
    _ensure_users_table()
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT ak.key_id, ak.user_id, ak.name, u.username, u.role
            FROM api_keys ak
            JOIN users u ON ak.user_id = u.user_id
            WHERE ak.key_hash = ?
            """,
            (key_hash,),
        ).fetchone()

        if not row:
            return None

        # Update last used
        conn.execute(
            "UPDATE api_keys SET last_used = CURRENT_TIMESTAMP WHERE key_id = ?",
            (row["key_id"],),
        )
        conn.commit()

        return dict(row)
    finally:
        conn.close()


def list_api_keys(user_id: str) -> list:
    """List API keys for a user (without the raw key)."""
    _ensure_users_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT key_id, key_prefix, name, created_at, last_used FROM api_keys WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_api_key(user_id: str, key_id: str) -> bool:
    """Delete an API key."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "DELETE FROM api_keys WHERE key_id = ? AND user_id = ?",
            (key_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
