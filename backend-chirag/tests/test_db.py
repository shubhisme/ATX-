"""
Unit tests for the SQLite Database Layer (backend/db.py).
Tests all CRUD operations, commit-SHA cache, supersession, and telemetry aggregation.
"""

import asyncio
import os
import sys
import unittest
import uuid

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from db import (
    init_db,
    create_job,
    update_job_status,
    get_job,
    list_jobs,
    supersede_pr_jobs,
    check_cache,
    store_cache,
    store_findings,
    store_gate_results,
    get_telemetry_summary,
    compute_diff_hash,
)


class TestDatabaseLayer(unittest.TestCase):
    def setUp(self):
        self.test_db = os.path.join(BACKEND_DIR, f"test_{uuid.uuid4().hex[:8]}.db")
        asyncio.run(init_db(self.test_db))

    def tearDown(self):
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except Exception:
                pass

    def test_job_crud_lifecycle(self):
        async def run():
            # 1. Create Job
            job = await create_job(
                commit_sha="abc123456789",
                pr_number=42,
                repo_url="https://github.com/test/repo",
                diff_content="+ line 1",
                db_path=self.test_db,
            )
            self.assertEqual(job["status"], "QUEUED")
            self.assertEqual(job["pr_number"], 42)

            # 2. Get Job
            fetched = await get_job(job["job_id"], db_path=self.test_db)
            self.assertIsNotNone(fetched)
            self.assertEqual(fetched["commit_sha"], "abc123456789")

            # 3. Update Status
            await update_job_status(
                job["job_id"],
                status="AI_REVIEWING",
                started_at=100.0,
                db_path=self.test_db,
            )
            updated = await get_job(job["job_id"], db_path=self.test_db)
            self.assertEqual(updated["status"], "AI_REVIEWING")
            self.assertEqual(updated["started_at"], 100.0)

            # 4. Complete Job
            await update_job_status(
                job["job_id"],
                status="COMPLETED",
                completed_at=105.0,
                latency_ms=5000,
                db_path=self.test_db,
            )
            completed = await get_job(job["job_id"], db_path=self.test_db)
            self.assertEqual(completed["status"], "COMPLETED")
            self.assertEqual(completed["latency_ms"], 5000)

            # 5. List Jobs
            all_jobs = await list_jobs(db_path=self.test_db)
            self.assertEqual(len(all_jobs), 1)

        asyncio.run(run())

    def test_supersession(self):
        async def run():
            # Job 1 on PR #10
            j1 = await create_job(
                commit_sha="commit_1",
                pr_number=10,
                status="QUEUED",
                db_path=self.test_db,
            )
            # Job 2 on PR #10 (supersedes Job 1)
            j2 = await create_job(
                commit_sha="commit_2",
                pr_number=10,
                status="QUEUED",
                db_path=self.test_db,
            )

            superseded_count = await supersede_pr_jobs(
                pr_number=10,
                exclude_job_id=j2["job_id"],
                db_path=self.test_db,
            )
            self.assertEqual(superseded_count, 1)

            res1 = await get_job(j1["job_id"], db_path=self.test_db)
            res2 = await get_job(j2["job_id"], db_path=self.test_db)

            self.assertEqual(res1["status"], "SUPERSEDED")
            self.assertEqual(res2["status"], "QUEUED")

        asyncio.run(run())

    def test_review_cache(self):
        async def run():
            sha = "sha_cache_test_999"
            cached = await check_cache(sha, db_path=self.test_db)
            self.assertIsNone(cached)

            diff = "--- a/test.py\n+++ b/test.py\n+pass\n"
            d_hash = compute_diff_hash(diff)
            review_payload = {
                "findings": [{"message": "Looks great"}],
                "summary": "Clean PR",
            }

            await store_cache(
                commit_sha=sha,
                diff_hash=d_hash,
                review_data=review_payload,
                tokens_in=100,
                tokens_out=50,
                cost_usd=0.0015,
                db_path=self.test_db,
            )

            cached_now = await check_cache(sha, db_path=self.test_db)
            self.assertIsNotNone(cached_now)
            self.assertEqual(cached_now["commit_sha"], sha)
            self.assertEqual(cached_now["review_data"]["summary"], "Clean PR")
            self.assertEqual(cached_now["tokens_in"], 100)

        asyncio.run(run())

    def test_findings_and_gate_storage(self):
        async def run():
            job = await create_job(
                commit_sha="sha_findings_test",
                db_path=self.test_db,
            )
            j_id = job["job_id"]

            # Store gate results
            gates = [
                {"check_type": "secret_scan", "passed": True, "details": [], "duration_ms": 1.2},
                {"check_type": "syntax_check", "passed": True, "details": [], "duration_ms": 0.8},
            ]
            await store_gate_results(j_id, gates, db_path=self.test_db)

            # Store findings
            findings = [
                {
                    "file_path": "auth.py",
                    "line_number": 12,
                    "severity": "warning",
                    "category": "security",
                    "message": "Token duration too long",
                    "suggestion": "Reduce to 3600",
                }
            ]
            await store_findings(j_id, findings, db_path=self.test_db)

            # Fetch complete job
            full_job = await get_job(j_id, db_path=self.test_db)
            self.assertEqual(len(full_job["gate_results"]), 2)
            self.assertEqual(len(full_job["findings"]), 1)
            self.assertEqual(full_job["findings"][0]["severity"], "warning")

            # Check telemetry summary
            telemetry = await get_telemetry_summary(db_path=self.test_db)
            self.assertEqual(telemetry["total_jobs"], 1)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
