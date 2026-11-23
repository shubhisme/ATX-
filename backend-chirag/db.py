"""
Database Layer — SQLite persistence with async support via aiosqlite.

Manages tables:
1. jobs — Full lifecycle tracking (QUEUED, STATIC_FAILED, AI_REVIEWING, COMPLETED, SUPERSEDED, FAILED)
2. review_cache — Commit-SHA deduplication cache for instant zero-token responses
3. review_findings — Inline AI review comments and suggestions
4. static_gate_results — Deterministic gate validation outcomes
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from typing import Any, Optional

import aiosqlite

from config import DATABASE_PATH

logger = logging.getLogger(__name__)


def get_db_path(override_path: Optional[str] = None) -> str:
    """Return configured database path."""
    return override_path or DATABASE_PATH or "pr_engine.db"


async def init_db(db_path: Optional[str] = None) -> None:
    """Initialize database tables and enable WAL mode for high concurrency."""
    path = get_db_path(db_path)
    async with aiosqlite.connect(path) as db:
        await db.execute("PRAGMA journal_mode = WAL;")
        await db.execute("PRAGMA foreign_keys = ON;")

        # 1. jobs table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                pr_number INTEGER,
                repo_url TEXT,
                commit_sha TEXT NOT NULL,
                status TEXT NOT NULL,
                diff_content TEXT,
                created_at REAL NOT NULL,
                started_at REAL,
                completed_at REAL,
                latency_ms INTEGER
            );
            """
        )
        await db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_pr_number ON jobs(pr_number);")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_jobs_commit_sha ON jobs(commit_sha);")

        # 2. review_cache table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS review_cache (
                commit_sha TEXT PRIMARY KEY,
                diff_hash TEXT NOT NULL,
                review_json TEXT NOT NULL,
                tokens_in INTEGER NOT NULL,
                tokens_out INTEGER NOT NULL,
                cost_usd REAL NOT NULL,
                created_at REAL NOT NULL
            );
            """
        )

        # 3. review_findings table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS review_findings (
                finding_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                line_number INTEGER,
                severity TEXT NOT NULL,
                category TEXT NOT NULL,
                message TEXT NOT NULL,
                suggestion TEXT,
                FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
            );
            """
        )
        await db.execute("CREATE INDEX IF NOT EXISTS idx_findings_job_id ON review_findings(job_id);")

        # 4. static_gate_results table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS static_gate_results (
                gate_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                check_type TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT NOT NULL,
                duration_ms REAL NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
            );
            """
        )
        await db.execute("CREATE INDEX IF NOT EXISTS idx_gates_job_id ON static_gate_results(job_id);")

        await db.commit()
    logger.info("Database initialized successfully at %s", path)


# ---------------------------------------------------------------------------
# Job Operations
# ---------------------------------------------------------------------------


async def create_job(
    commit_sha: str,
    pr_number: Optional[int] = None,
    repo_url: Optional[str] = None,
    diff_content: str = "",
    status: str = "QUEUED",
    job_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    """Create a new job record."""
    path = get_db_path(db_path)
    j_id = job_id or uuid.uuid4().hex
    now = time.time()

    async with aiosqlite.connect(path) as db:
        await db.execute(
            """
            INSERT INTO jobs (
                job_id, pr_number, repo_url, commit_sha, status, diff_content, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (j_id, pr_number, repo_url, commit_sha, status, diff_content, now),
        )
        await db.commit()

    return {
        "job_id": j_id,
        "pr_number": pr_number,
        "repo_url": repo_url,
        "commit_sha": commit_sha,
        "status": status,
        "diff_content": diff_content,
        "created_at": now,
        "started_at": None,
        "completed_at": None,
        "latency_ms": None,
    }


async def update_job_status(
    job_id: str,
    status: str,
    started_at: Optional[float] = None,
    completed_at: Optional[float] = None,
    latency_ms: Optional[int] = None,
    db_path: Optional[str] = None,
) -> None:
    """Update job lifecycle status and optional timestamps."""
    path = get_db_path(db_path)
    fields = ["status = ?"]
    params: list[Any] = [status]

    if started_at is not None:
        fields.append("started_at = ?")
        params.append(started_at)
    if completed_at is not None:
        fields.append("completed_at = ?")
        params.append(completed_at)
    if latency_ms is not None:
        fields.append("latency_ms = ?")
        params.append(latency_ms)

    params.append(job_id)
    query = f"UPDATE jobs SET {', '.join(fields)} WHERE job_id = ?;"

    async with aiosqlite.connect(path) as db:
        await db.execute(query, params)
        await db.commit()


async def get_job(job_id: str, db_path: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Fetch complete job details including findings and gate results."""
    path = get_db_path(db_path)
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("SELECT * FROM jobs WHERE job_id = ?;", (job_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            job_data = dict(row)

        # Fetch findings
        async with db.execute(
            "SELECT * FROM review_findings WHERE job_id = ?;", (job_id,)
        ) as cursor:
            findings_rows = await cursor.fetchall()
            job_data["findings"] = [dict(r) for r in findings_rows]

        # Fetch gate results
        async with db.execute(
            "SELECT * FROM static_gate_results WHERE job_id = ?;", (job_id,)
        ) as cursor:
            gate_rows = await cursor.fetchall()
            gates = []
            for r in gate_rows:
                g_dict = dict(r)
                try:
                    g_dict["details"] = json.loads(g_dict["details"])
                except Exception:
                    pass
                gates.append(g_dict)
            job_data["gate_results"] = gates

    return job_data


async def list_jobs(
    limit: int = 50,
    offset: int = 0,
    db_path: Optional[str] = None,
) -> list[dict[str, Any]]:
    """List recent jobs for the dashboard monitor."""
    path = get_db_path(db_path)
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT job_id, pr_number, repo_url, commit_sha, status, created_at, started_at, completed_at, latency_ms
            FROM jobs
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?;
            """,
            (limit, offset),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def supersede_pr_jobs(
    pr_number: int,
    exclude_job_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> int:
    """Supersede active or queued jobs for a PR when a newer commit arrives."""
    path = get_db_path(db_path)
    query = """
        UPDATE jobs
        SET status = 'SUPERSEDED'
        WHERE pr_number = ?
          AND status IN ('QUEUED', 'AI_REVIEWING')
    """
    params: list[Any] = [pr_number]
    if exclude_job_id:
        query += " AND job_id != ?"
        params.append(exclude_job_id)

    async with aiosqlite.connect(path) as db:
        cursor = await db.execute(query, params)
        await db.commit()
        return cursor.rowcount


# ---------------------------------------------------------------------------
# Cache Operations
# ---------------------------------------------------------------------------


def compute_diff_hash(diff_content: str) -> str:
    """Compute SHA-256 hash of unified diff content."""
    return hashlib.sha256(diff_content.encode("utf-8")).hexdigest()


async def check_cache(
    commit_sha: str,
    db_path: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Check if review result is cached for the given commit SHA."""
    path = get_db_path(db_path)
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM review_cache WHERE commit_sha = ?;", (commit_sha,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            try:
                res["review_data"] = json.loads(res["review_json"])
            except Exception:
                res["review_data"] = {}
            return res


async def store_cache(
    commit_sha: str,
    diff_hash: str,
    review_data: dict[str, Any],
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
    db_path: Optional[str] = None,
) -> None:
    """Store review result in commit-SHA cache."""
    path = get_db_path(db_path)
    review_json = json.dumps(review_data)
    now = time.time()

    async with aiosqlite.connect(path) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO review_cache (
                commit_sha, diff_hash, review_json, tokens_in, tokens_out, cost_usd, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (commit_sha, diff_hash, review_json, tokens_in, tokens_out, cost_usd, now),
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Findings & Gate Results Operations
# ---------------------------------------------------------------------------


async def store_findings(
    job_id: str,
    findings: list[dict[str, Any]],
    db_path: Optional[str] = None,
) -> None:
    """Bulk insert findings for a completed review."""
    if not findings:
        return

    path = get_db_path(db_path)
    records = []
    for f in findings:
        records.append(
            (
                uuid.uuid4().hex,
                job_id,
                str(f.get("file_path", "")),
                f.get("line_number"),
                str(f.get("severity", "info")),
                str(f.get("category", "style")),
                str(f.get("message", "")),
                f.get("suggestion"),
            )
        )

    async with aiosqlite.connect(path) as db:
        await db.executemany(
            """
            INSERT INTO review_findings (
                finding_id, job_id, file_path, line_number, severity, category, message, suggestion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            records,
        )
        await db.commit()


async def store_gate_results(
    job_id: str,
    checks: list[dict[str, Any]],
    db_path: Optional[str] = None,
) -> None:
    """Insert deterministic gate check results."""
    if not checks:
        return

    path = get_db_path(db_path)
    records = []
    for c in checks:
        details_str = (
            json.dumps(c.get("details", []))
            if isinstance(c.get("details"), (list, dict))
            else str(c.get("details", ""))
        )
        status_str = "PASSED" if c.get("passed") else "FAILED"
        records.append(
            (
                uuid.uuid4().hex,
                job_id,
                str(c.get("check_type", "gate")),
                status_str,
                details_str,
                float(c.get("duration_ms", 0.0)),
            )
        )

    async with aiosqlite.connect(path) as db:
        await db.executemany(
            """
            INSERT INTO static_gate_results (
                gate_id, job_id, check_type, status, details, duration_ms
            ) VALUES (?, ?, ?, ?, ?, ?);
            """,
            records,
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Telemetry Aggregation
# ---------------------------------------------------------------------------


async def get_telemetry_summary(db_path: Optional[str] = None) -> dict[str, Any]:
    """Calculate aggregate telemetry metrics across all PR jobs."""
    path = get_db_path(db_path)
    async with aiosqlite.connect(path) as db:
        # Total counts by status
        async with db.execute(
            """
            SELECT
                COUNT(*) as total_jobs,
                SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed_jobs,
                SUM(CASE WHEN status = 'STATIC_FAILED' OR status = 'FAILED' THEN 1 ELSE 0 END) as failed_jobs,
                SUM(CASE WHEN status = 'SUPERSEDED' THEN 1 ELSE 0 END) as superseded_jobs,
                AVG(CASE WHEN latency_ms IS NOT NULL THEN latency_ms ELSE NULL END) as avg_latency_ms
            FROM jobs;
            """
        ) as cursor:
            row = await cursor.fetchone()
            total_jobs = row[0] or 0
            completed_jobs = row[1] or 0
            failed_jobs = row[2] or 0
            superseded_jobs = row[3] or 0
            avg_latency_ms = round(row[4] or 0.0, 2)

        # Cache metrics & token sums from review_cache
        async with db.execute(
            """
            SELECT
                COUNT(*) as cached_records,
                COALESCE(SUM(tokens_in + tokens_out), 0) as total_tokens,
                COALESCE(SUM(cost_usd), 0.0) as total_cost_usd
            FROM review_cache;
            """
        ) as cursor:
            cache_row = await cursor.fetchone()
            cached_records = cache_row[0] or 0
            total_tokens = cache_row[1] or 0
            total_cost_usd = round(cache_row[2] or 0.0, 6)

        cache_hit_rate = (
            round((cached_records / total_jobs) * 100, 2) if total_jobs > 0 else 0.0
        )

    return {
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "failed_jobs": failed_jobs,
        "superseded_jobs": superseded_jobs,
        "cached_jobs": cached_records,
        "avg_latency_ms": avg_latency_ms,
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost_usd,
        "cache_hit_rate": cache_hit_rate,
    }
