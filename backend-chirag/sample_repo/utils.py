"""General-purpose utility functions.

This module has no internal project imports and serves as the
lowest-level dependency in the sample repository.
"""

import re
import uuid
from datetime import datetime, timezone
from typing import Any


def sanitize_input(text: str) -> str:
    """Strip dangerous characters and collapse whitespace.

    Args:
        text: Raw user-supplied string.

    Returns:
        A sanitized copy of the string safe for further processing.
    """
    cleaned = re.sub(r"[<>&\"']", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def format_response(data: Any, status: int = 200) -> dict[str, Any]:
    """Wrap *data* in a standard API response envelope.

    Args:
        data: Payload to include in the response body.
        status: HTTP-style status code.

    Returns:
        A dictionary with ``status``, ``data``, and ``timestamp`` keys.
    """
    return {
        "status": status,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def validate_email(email: str) -> bool:
    """Check whether *email* looks like a valid e-mail address.

    Args:
        email: The address to validate.

    Returns:
        ``True`` when the address matches a basic e-mail pattern.
    """
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))


def generate_id() -> str:
    """Generate a unique identifier string.

    Returns:
        A UUID-4 hex string (32 characters, no dashes).
    """
    return uuid.uuid4().hex
