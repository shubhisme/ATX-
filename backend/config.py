"""
Application configuration loaded from environment variables.
Import this module everywhere instead of calling os.getenv directly.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load from backend/.env or root .env
_backend_dir = Path(__file__).resolve().parent
load_dotenv(dotenv_path=_backend_dir / ".env")
load_dotenv(dotenv_path=_backend_dir.parent / ".env")
load_dotenv()

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
GITHUB_WEBHOOK_SECRET: str = os.getenv("GITHUB_WEBHOOK_SECRET", "")

DB_PATH: str = os.getenv("DB_PATH", "pr_engine.db")
NUM_WORKERS: int = int(os.getenv("NUM_WORKERS", "3"))
API_PORT: int = int(os.getenv("API_PORT", "8000"))

MAX_DIFF_SIZE: int = 100_000
MAX_BATCH_SIZE: int = 20
TOKEN_BUDGET: int = 4_000
