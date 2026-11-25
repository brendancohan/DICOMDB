import hashlib
import hmac
import os
import sqlite3
from typing import Optional

from fastapi import Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings

SESSION_COOKIE_NAME = "dicomdb_session"
SESSION_MAX_AGE = 60 * 60 * 12  # 12 hours


def hash_password(password: str) -> str:
    """Hash a password using stdlib scrypt with a 16-byte random salt."""
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored salt$hash string."""
    if "$" not in stored_hash:
        return False
    salt_hex, hash_hex = stored_hash.split("$", 1)
    try:
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except ValueError:
        return False
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return hmac.compare_digest(dk, expected)


def ensure_default_password(conn: sqlite3.Connection) -> None:
    """Seed the shared account password hash on first startup if not present."""
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'password_hash'"
    ).fetchone()
    if row is None:
        hashed = hash_password(settings.default_password)
        conn.execute(
            "INSERT INTO settings (key, value) VALUES ('password_hash', ?)",
            (hashed,),
        )
        conn.commit()


def set_password(conn: sqlite3.Connection, new_password: str) -> None:
    """Update the shared account password hash in settings."""
    hashed = hash_password(new_password)
    conn.execute(
        "INSERT INTO settings (key, value) VALUES ('password_hash', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (hashed,),
    )
    conn.commit()


def authenticate_user(conn: sqlite3.Connection, username: str, password: str) -> bool:
    """Verify username and password against the single shared local account."""
    if not hmac.compare_digest(username.strip(), settings.username):
        return False
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'password_hash'"
    ).fetchone()
    if row is None:
        return False
    return verify_password(password, row["value"])


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt="dicomdb-session")


def create_session_token(username: str) -> str:
    return _serializer().dumps({"u": username})


def verify_session_token(token: str) -> Optional[str]:
    try:
        data = _serializer().loads(token, max_age=SESSION_MAX_AGE)
        return data.get("u")
    except (BadSignature, SignatureExpired):
        return None


def get_current_user(request: Request) -> Optional[str]:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    return verify_session_token(token)


def get_editor_label(request: Request, form_editor: Optional[str] = None) -> str:
    """Return optional staff initials/name for audit attribution, falling back to username."""
    candidate = (form_editor or request.headers.get("X-Editor-Label") or "").strip()
    if candidate:
        return candidate[:64]
    return get_current_user(request) or settings.username
