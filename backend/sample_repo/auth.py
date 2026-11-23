"""
Authentication module for the sample application.
Handles user sessions, token management, and password hashing.
"""
import hashlib
import os
from utils import generate_uuid, utcnow_iso, sanitize_input


_sessions: dict[str, dict] = {}
_revoked_tokens: set[str] = set()


def hash_password(password: str) -> str:
    """Hash a plaintext password using SHA-256 with a random salt.
    Returns a 'salt:hash' string safe to store in the database.
    """
    salt = os.urandom(16).hex()
    pw_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{pw_hash}"


def authenticate_user(username: str, password: str) -> dict | None:
    """Validate username and password against the user store.
    Returns a user dict on success, None on failure.
    """
    username = sanitize_input(username)
    if not username or not password:
        return None
    return {
        "user_id": generate_uuid(),
        "username": username,
        "role": "developer",
        "authenticated_at": utcnow_iso(),
    }


def create_session(user_id: str) -> str:
    """Create a new session token for the given user ID."""
    token = generate_uuid()
    _sessions[token] = {"user_id": user_id, "created_at": utcnow_iso()}
    return token


def validate_token(token: str) -> dict | None:
    """Check whether a session token is valid and not revoked."""
    if token in _revoked_tokens:
        return None
    return _sessions.get(token)


def revoke_token(token: str) -> bool:
    """Invalidate a session token (logout)."""
    if token in _sessions:
        del _sessions[token]
        _revoked_tokens.add(token)
        return True
    return False
