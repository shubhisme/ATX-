"""Authentication and session management helpers.

Depends on :mod:`utils` for ID generation and input sanitization,
and on :mod:`config` for the secret key and token expiry settings.
"""

import hashlib
import hmac
import time
from typing import Any, Optional

from .config import SECRET_KEY, TOKEN_EXPIRY_SECONDS
from .utils import generate_id, sanitize_input


def hash_password(password: str) -> str:
    """Return a salted SHA-256 hex digest of *password*.

    Args:
        password: Plain-text password to hash.

    Returns:
        A hex-encoded hash string.
    """
    salted = f"{SECRET_KEY}:{password}"
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()


def verify_token(token: str) -> dict[str, Any]:
    """Validate *token* and return its decoded claims.

    A token is formatted as ``<user_id>:<timestamp>:<signature>``.

    Args:
        token: The bearer token string.

    Returns:
        A dict with ``valid`` (bool), ``user_id`` (str | None),
        and ``reason`` (str | None) keys.
    """
    token = sanitize_input(token)
    parts = token.split(":")
    if len(parts) != 3:
        return {"valid": False, "user_id": None, "reason": "malformed token"}

    user_id, timestamp_str, signature = parts
    try:
        issued_at = float(timestamp_str)
    except ValueError:
        return {"valid": False, "user_id": None, "reason": "invalid timestamp"}

    if time.time() - issued_at > TOKEN_EXPIRY_SECONDS:
        return {"valid": False, "user_id": None, "reason": "token expired"}

    expected = hmac.new(
        SECRET_KEY.encode(), f"{user_id}:{timestamp_str}".encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        return {"valid": False, "user_id": None, "reason": "bad signature"}

    return {"valid": True, "user_id": user_id, "reason": None}


def create_session(user_id: str) -> dict[str, str]:
    """Create a new authenticated session for *user_id*.

    Args:
        user_id: Identifier of the user to create a session for.

    Returns:
        A dict containing ``session_id`` and ``token``.
    """
    session_id = generate_id()
    timestamp = str(time.time())
    signature = hmac.new(
        SECRET_KEY.encode(), f"{user_id}:{timestamp}".encode(), hashlib.sha256
    ).hexdigest()
    token = f"{user_id}:{timestamp}:{signature}"
    return {"session_id": session_id, "token": token}
