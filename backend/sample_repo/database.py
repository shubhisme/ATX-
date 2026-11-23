"""Database access layer.

Provides connection management and query helpers.  Depends on
:mod:`config` for the connection string and :mod:`utils` for
input sanitization and ID generation.
"""

from typing import Any, Optional

from .config import DATABASE_URL, MAX_RETRIES
from .utils import generate_id, sanitize_input


# In-memory store used for testing without a real database.
_STORE: dict[str, list[dict[str, Any]]] = {}


def get_connection() -> dict[str, Any]:
    """Return a lightweight connection-info dictionary.

    In a real application this would return a database connection
    object; here it returns metadata suitable for testing.

    Returns:
        A dict describing the connection.
    """
    return {
        "url": DATABASE_URL,
        "max_retries": MAX_RETRIES,
        "connected": True,
    }


def execute_query(query: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Execute a raw SQL-style *query* with optional *params*.

    Args:
        query: The SQL query string.
        params: Bind parameters for the query.

    Returns:
        A dict with ``success``, ``query``, and ``params`` keys.
    """
    sanitized_query = sanitize_input(query)
    return {
        "success": True,
        "query": sanitized_query,
        "params": params or {},
    }


def fetch_user(user_id: str) -> Optional[dict[str, Any]]:
    """Look up a user record by *user_id*.

    Args:
        user_id: The unique identifier of the user.

    Returns:
        A user dict if found, otherwise ``None``.
    """
    users = _STORE.get("users", [])
    for user in users:
        if user.get("id") == user_id:
            return user
    return None


def save_record(table: str, data: dict[str, Any]) -> dict[str, Any]:
    """Persist *data* into the in-memory *table*.

    A generated ID is attached if one is not already present.

    Args:
        table: Name of the target table / collection.
        data: The record to store.

    Returns:
        A dict with ``success``, ``table``, and ``record_id`` keys.
    """
    if table not in _STORE:
        _STORE[table] = []

    record = dict(data)
    if "id" not in record:
        record["id"] = generate_id()

    _STORE[table].append(record)
    return {"success": True, "table": table, "record_id": record["id"]}
