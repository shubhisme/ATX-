"""
Utility helpers used across the sample application.
No local imports — standalone module.
"""
import uuid
import re
from datetime import datetime, timezone


def generate_uuid() -> str:
    """Generate a new random UUID4 string."""
    return str(uuid.uuid4())


def utcnow_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sanitize_input(text: str) -> str:
    """Strip leading/trailing whitespace and remove control characters."""
    text = text.strip()
    text = re.sub(r"[\x00-\x1f\x7f]", "", text)
    return text


def format_currency(amount: float, currency: str = "USD") -> str:
    """Format a float amount as a currency string, e.g. '$12.50'."""
    symbols = {"USD": "$", "EUR": "€", "GBP": "£"}
    symbol = symbols.get(currency.upper(), currency + " ")
    return f"{symbol}{amount:,.2f}"


def validate_email(email: str) -> bool:
    """Return True if the string looks like a valid email address."""
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def truncate(text: str, max_len: int = 100) -> str:
    """Truncate text to max_len characters, appending '...' if cut."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
