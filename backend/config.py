"""
Application configuration loaded from environment variables.
Import this module everywhere instead of calling os.getenv directly.
"""
import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
GITHUB_WEBHOOK_SECRET: str = os.getenv("GITHUB_WEBHOOK_SECRET", "")

DB_PATH: str = os.getenv("DB_PATH", "pr_engine.db")
NUM_WORKERS: int = int(os.getenv("NUM_WORKERS", "3"))
API_PORT: int = int(os.getenv("API_PORT", "8000"))

MAX_DIFF_SIZE: int = 100_000
MAX_BATCH_SIZE: int = 20
TOKEN_BUDGET: int = 4_000
