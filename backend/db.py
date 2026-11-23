"""
SQLite database layer using aiosqlite for async operations.
Handles job persistence, commit caching, and telemetry storage.
"""
import json
import aiosqlite
from typing import Optional
from datetime import datetime
from models import PRJobRow, PRJobInsert, PRStatus, CacheRow, CacheInsert
from config import DB_PATH


async def init_db():
    """Initialize database schema with WAL mode enabled."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Enable WAL mode for better concurrency
        await db.execute("PRAGMA journal_mode=WAL")
        
        # Jobs table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pr_number INTEGER NOT NULL,
                title TEXT NOT NULL,
                commit_sha TEXT NOT NULL,
                diff TEXT NOT NULL,
                status TEXT NOT NULL,
                files TEXT NOT NULL,
                static_result TEXT,
                review TEXT,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                cost_usd REAL,
                queued_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                latency_ms INTEGER,
                cache_hit INTEGER DEFAULT 0
            )
        """)
        
        # Commit cache table - keyed by repo + commit_sha
        await db.execute("""
            CREATE TABLE IF NOT EXISTS commit_cache (
                commit_sha TEXT PRIMARY KEY,
                review TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL,
                completion_tokens INTEGER NOT NULL,
                cost_usd REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        # Create indices for performance
        await db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_commit ON jobs(commit_sha)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_pr ON jobs(pr_number)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
        
        # Check if database is empty; if so, populate initial realistic demo jobs
        cursor = await db.execute("SELECT COUNT(*) FROM jobs")
        count = (await cursor.fetchone())[0]
        if count == 0:
            await _seed_demo_data(db)
            
        await db.commit()


async def _seed_demo_data(db: aiosqlite.Connection):
    """Seed initial prototype demo data for rich instant out-of-the-box demonstration."""
    now = datetime.utcnow().isoformat() + "Z"
    
    # 1. SQL Injection job
    sql_findings = {
        "summary": "Security vulnerability detected: Potential SQL Injection.",
        "findings": [{
            "severity": "critical",
            "file": "database.py",
            "line": 5,
            "message": "Direct f-string interpolation into SQL statement introduces SQL Injection vulnerability (CWE-89).",
            "suggestion": "Use parameterized queries: return db.query('SELECT * FROM users WHERE id = ?', (uid,))"
        }]
    }
    await db.execute("""
        INSERT INTO jobs (
            pr_number, title, commit_sha, diff, status, files, static_result, review,
            prompt_tokens, completion_tokens, cost_usd, queued_at, started_at, completed_at, latency_ms, cache_hit
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        101, "PR #101: SQL Injection Flaw", "a3f9c2e81b7d4c05a1e2f3b4c5d6e7f801234567",
        "--- a/database.py\n+++ b/database.py\n@@ -4,3 +4,3 @@\n def get_user(uid):\n-    return db.query(\"SELECT * FROM users WHERE id = ?\", uid)\n+    return db.query(f\"SELECT * FROM users WHERE id = {uid}\")",
        PRStatus.COMPLETED.value, json.dumps(["database.py"]),
        json.dumps({"passed": True, "errors": [], "warnings": []}),
        json.dumps(sql_findings),
        2140, 385, 0.001566, now, now, now, 2600, 0
    ))

    # 2. Secret leak static failure
    await db.execute("""
        INSERT INTO jobs (
            pr_number, title, commit_sha, diff, status, files, static_result, review,
            prompt_tokens, completion_tokens, cost_usd, queued_at, started_at, completed_at, latency_ms, cache_hit
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        102, "PR #102: Hardcoded AWS Key Leak", "b81c0d9e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c",
        "--- a/config.py\n+++ b/config.py\n@@ -1,2 +1,3 @@\n+AWS_KEY = \"AKIAIOSFODNN7EXAMPLE\"\n DEBUG = True",
        PRStatus.STATIC_FAILED.value, json.dumps(["config.py"]),
        json.dumps({"passed": False, "errors": ["Hardcoded AWS Access Key pattern matched at config.py:1"], "warnings": []}),
        None,
        0, 0, 0.0, now, now, now, 10, 0
    ))

    # 3. Cache hit job
    await db.execute("""
        INSERT INTO jobs (
            pr_number, title, commit_sha, diff, status, files, static_result, review,
            prompt_tokens, completion_tokens, cost_usd, queued_at, started_at, completed_at, latency_ms, cache_hit
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        103, "PR #103: Deduplication Cache Test", "a3f9c2e81b7d4c05a1e2f3b4c5d6e7f801234567",
        "--- a/database.py\n+++ b/database.py\n@@ -4,3 +4,3 @@\n def get_user(uid):\n-    return db.query(\"SELECT * FROM users WHERE id = ?\", uid)\n+    return db.query(f\"SELECT * FROM users WHERE id = {uid}\")",
        PRStatus.COMPLETED.value, json.dumps(["database.py"]),
        json.dumps({"passed": True, "errors": [], "warnings": []}),
        json.dumps(sql_findings),
        0, 0, 0.0, now, now, now, 12, 1
    ))

    # 4. Missing import job
    import_findings = {
        "summary": "Import error identified in auth routine.",
        "findings": [{
            "severity": "warning",
            "file": "auth.py",
            "line": 11,
            "message": "Symbol 'check_hash' is invoked without being imported in this file.",
            "suggestion": "Add top-level import: from utils import check_hash"
        }]
    }
    await db.execute("""
        INSERT INTO jobs (
            pr_number, title, commit_sha, diff, status, files, static_result, review,
            prompt_tokens, completion_tokens, cost_usd, queued_at, started_at, completed_at, latency_ms, cache_hit
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        104, "PR #104: Missing Import & Unsalted Hash", "c92d1e0f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d",
        "--- a/auth.py\n+++ b/auth.py\n@@ -10,4 +10,4 @@\n def login(user, password):\n-    if password == \"admin123\":\n+    if check_hash(password, user.hash):\n         return True",
        PRStatus.COMPLETED.value, json.dumps(["auth.py"]),
        json.dumps({"passed": True, "errors": [], "warnings": []}),
        json.dumps(import_findings),
        1920, 310, 0.001377, now, now, now, 2600, 0
    ))

    # 5. Clean docstring job
    await db.execute("""
        INSERT INTO jobs (
            pr_number, title, commit_sha, diff, status, files, static_result, review,
            prompt_tokens, completion_tokens, cost_usd, queued_at, started_at, completed_at, latency_ms, cache_hit
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        105, "PR #105: Clean change (Docstring)", "d03e2f1a9b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e",
        "--- a/utils.py\n+++ b/utils.py\n@@ -1,3 +1,4 @@\n def helper(x):\n+    \"\"\"Return x doubled.\"\"\"\n     return x * 2",
        PRStatus.COMPLETED.value, json.dumps(["utils.py"]),
        json.dumps({"passed": True, "errors": [], "warnings": []}),
        json.dumps({"summary": "Clean modification. No defects found.", "findings": []}),
        1280, 190, 0.000905, now, now, now, 2100, 0
    ))

    # 6. Superseded job
    await db.execute("""
        INSERT INTO jobs (
            pr_number, title, commit_sha, diff, status, files, static_result, review,
            prompt_tokens, completion_tokens, cost_usd, queued_at, started_at, completed_at, latency_ms, cache_hit
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        106, "PR #106: Superseded Version Bump", "e14f3a2b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f",
        "--- a/app.py\n+++ b/app.py\n@@ -1,2 +1,2 @@\n-VERSION = 1\n+VERSION = 2",
        PRStatus.SUPERSEDED.value, json.dumps(["app.py"]),
        None, None,
        0, 0, 0.0, now, now, now, 800, 0
    ))

    # Commit cache entry
    await db.execute("""
        INSERT OR REPLACE INTO commit_cache (
            commit_sha, review, prompt_tokens, completion_tokens, cost_usd, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "a3f9c2e81b7d4c05a1e2f3b4c5d6e7f801234567",
        json.dumps(sql_findings),
        2140, 385, 0.001566, now
    ))


async def insert_job(job: PRJobInsert) -> int:
    """Insert a new job and return its ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO jobs (
                pr_number, title, commit_sha, diff, status, files, queued_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            job.pr_number,
            job.title,
            job.commit_sha,
            job.diff,
            PRStatus.QUEUED.value,
            json.dumps(job.files),
            job.queued_at
        ))
        await db.commit()
        return cursor.lastrowid


async def get_job(job_id: int) -> Optional[PRJobRow]:
    """Fetch a single job by ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_job(row)


async def get_all_jobs(limit: int = 100) -> list[PRJobRow]:
    """Fetch all jobs, most recent first."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM jobs ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [_row_to_job(row) for row in rows]


async def update_job_status(job_id: int, status: PRStatus, started_at: Optional[str] = None):
    """Update job status and optionally set started_at timestamp."""
    async with aiosqlite.connect(DB_PATH) as db:
        if started_at:
            await db.execute(
                "UPDATE jobs SET status = ?, started_at = ? WHERE id = ?",
                (status.value, started_at, job_id)
            )
        else:
            await db.execute(
                "UPDATE jobs SET status = ? WHERE id = ?",
                (status.value, job_id)
            )
        await db.commit()


async def complete_job(
    job_id: int,
    status: PRStatus,
    static_result: Optional[dict] = None,
    review: Optional[dict] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    cost_usd: Optional[float] = None,
    completed_at: Optional[str] = None,
    latency_ms: Optional[int] = None,
    cache_hit: bool = False
):
    """Mark a job as complete with results and telemetry."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE jobs SET
                status = ?,
                static_result = ?,
                review = ?,
                prompt_tokens = ?,
                completion_tokens = ?,
                cost_usd = ?,
                completed_at = ?,
                latency_ms = ?,
                cache_hit = ?
            WHERE id = ?
        """, (
            status.value,
            json.dumps(static_result) if static_result else None,
            json.dumps(review) if review else None,
            prompt_tokens,
            completion_tokens,
            cost_usd,
            completed_at,
            latency_ms,
            1 if cache_hit else 0,
            job_id
        ))
        await db.commit()


async def supersede_old_jobs(pr_number: int, latest_commit_sha: str):
    """Mark all jobs for a PR that don't match the latest commit as SUPERSEDED."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE jobs 
            SET status = ? 
            WHERE pr_number = ? 
            AND commit_sha != ? 
            AND status NOT IN (?, ?)
        """, (
            PRStatus.SUPERSEDED.value,
            pr_number,
            latest_commit_sha,
            PRStatus.COMPLETED.value,
            PRStatus.SUPERSEDED.value
        ))
        await db.commit()


async def get_cache_hit(commit_sha: str) -> Optional[CacheRow]:
    """Check if a commit has been reviewed before."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM commit_cache WHERE commit_sha = ?",
            (commit_sha,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return CacheRow(
            commit_sha=row["commit_sha"],
            review=json.loads(row["review"]),
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            cost_usd=row["cost_usd"],
            created_at=row["created_at"]
        )


async def insert_cache(cache: CacheInsert):
    """Store a completed review in the commit cache."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO commit_cache (
                commit_sha, review, prompt_tokens, completion_tokens, cost_usd, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            cache.commit_sha,
            json.dumps(cache.review),
            cache.prompt_tokens,
            cache.completion_tokens,
            cache.cost_usd,
            cache.created_at
        ))
        await db.commit()


def _row_to_job(row: aiosqlite.Row) -> PRJobRow:
    """Convert a database row to a PRJobRow dataclass."""
    return PRJobRow(
        id=row["id"],
        pr_number=row["pr_number"],
        title=row["title"],
        commit_sha=row["commit_sha"],
        diff=row["diff"],
        status=PRStatus(row["status"]),
        files=json.loads(row["files"]),
        static_result=json.loads(row["static_result"]) if row["static_result"] else None,
        review=json.loads(row["review"]) if row["review"] else None,
        prompt_tokens=row["prompt_tokens"],
        completion_tokens=row["completion_tokens"],
        cost_usd=row["cost_usd"],
        queued_at=row["queued_at"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        latency_ms=row["latency_ms"],
        cache_hit=bool(row["cache_hit"])
    )
