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
        
        await db.commit()


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
