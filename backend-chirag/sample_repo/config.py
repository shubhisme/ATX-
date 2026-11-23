"""Application configuration constants.

Centralizes all configuration values used across the sample repository.
Modules should import specific constants rather than using wildcard imports.
"""

from typing import Final

# Database configuration
DATABASE_URL: Final[str] = "postgresql://localhost:5432/atx_placement"
DATABASE_POOL_SIZE: Final[int] = 10

# Authentication & security
SECRET_KEY: Final[str] = "dev-secret-key-change-in-production"
TOKEN_EXPIRY_SECONDS: Final[int] = 3600

# API settings
API_VERSION: Final[str] = "v1"
API_PREFIX: Final[str] = f"/api/{API_VERSION}"

# Retry / resilience
MAX_RETRIES: Final[int] = 3
RETRY_BACKOFF_FACTOR: Final[float] = 0.5

# Logging
LOG_LEVEL: Final[str] = "INFO"
LOG_FORMAT: Final[str] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def get_config_summary() -> dict[str, str | int]:
    """Return a dictionary summarizing the current configuration.

    Returns:
        A mapping of configuration key names to their values.
    """
    return {
        "database_url": DATABASE_URL,
        "api_version": API_VERSION,
        "max_retries": MAX_RETRIES,
        "log_level": LOG_LEVEL,
        "token_expiry": TOKEN_EXPIRY_SECONDS,
    }
