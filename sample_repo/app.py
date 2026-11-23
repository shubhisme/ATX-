"""Main application entry-point with route handlers.

Imports from :mod:`auth`, :mod:`database`, and :mod:`utils` to
exercise cross-module dependency resolution during PR verification.
"""

from typing import Any

from .auth import create_session, hash_password, verify_token
from .database import execute_query, fetch_user, save_record
from .utils import format_response, sanitize_input, validate_email


def register_user(email: str, password: str) -> dict[str, Any]:
    """Handle user registration.

    Validates the e-mail, hashes the password, persists the new user
    record, and returns a session.

    Args:
        email: The user's e-mail address.
        password: The plain-text password chosen by the user.

    Returns:
        A standard API response envelope.
    """
    email = sanitize_input(email)
    if not validate_email(email):
        return format_response({"error": "Invalid email address"}, status=400)

    hashed = hash_password(password)
    result = save_record("users", {"email": email, "password_hash": hashed})
    session = create_session(result["record_id"])
    return format_response({"user_id": result["record_id"], **session}, status=201)


def login_user(user_id: str, password: str) -> dict[str, Any]:
    """Authenticate an existing user and issue a session token.

    Args:
        user_id: The identifier of the user attempting to log in.
        password: The plain-text password supplied for verification.

    Returns:
        A standard API response envelope.
    """
    user = fetch_user(user_id)
    if user is None:
        return format_response({"error": "User not found"}, status=404)

    if user.get("password_hash") != hash_password(password):
        return format_response({"error": "Invalid credentials"}, status=401)

    session = create_session(user_id)
    return format_response({"message": "Login successful", **session})


def get_user_profile(token: str, user_id: str) -> dict[str, Any]:
    """Return the profile for *user_id* if *token* is valid.

    Args:
        token: Bearer token for authorization.
        user_id: The user whose profile is requested.

    Returns:
        A standard API response envelope.
    """
    claims = verify_token(token)
    if not claims["valid"]:
        return format_response({"error": claims["reason"]}, status=401)

    user = fetch_user(user_id)
    if user is None:
        return format_response({"error": "User not found"}, status=404)

    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    return format_response(safe_user)
