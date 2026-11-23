import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "compound-beta")
WORKER_POOL_SIZE = int(os.getenv("WORKER_POOL_SIZE", "3"))
DATABASE_PATH = os.getenv("DATABASE_PATH", "pr_engine.db")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
TOKEN_BUDGET = int(os.getenv("TOKEN_BUDGET", "4000"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
