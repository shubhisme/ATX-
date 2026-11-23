"""
Test script to demonstrate parallel queue processing with async workers.
This script submits multiple PRs and monitors how workers process them concurrently.
"""
import asyncio
import httpx
import time
from datetime import datetime
import pytest

pytestmark = pytest.mark.skip(reason="Integration script requiring running server at http://localhost:8000")


API_BASE = "http://localhost:8000"


async def submit_pr(pr_number: int, title: str, diff: str):
    """Submit a single PR."""
    commit_sha = f"{pr_number:040d}"
    
    payload = {
        "pr_number": pr_number,
        "title": title,
        "commit_sha": commit_sha,
        "diff": diff,
        "files": ["test.py"]
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{API_BASE}/submit", json=payload, timeout=10.0)
        return response.json()


async def get_status():
    """Get system status."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/status", timeout=5.0)
        return response.json()


async def get_job(job_id: int):
    """Get job details."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/jobs/{job_id}", timeout=5.0)
        return response.json()


async def monitor_workers(duration: int = 10):
    """Monitor worker status for a duration."""
    print("\n" + "="*70)
    print("MONITORING WORKERS")
    print("="*70)
    
    start = time.time()
    while (time.time() - start) < duration:
        try:
            status = await get_status()
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            queue_size = status["queue_size"]
            busy = status["busy_workers"]
            idle = status["idle_workers"]
            
            # Build worker display
            worker_display = []
            for worker in status["workers"]:
                wid = worker["worker_id"]
                wstatus = worker["status"]
                job_id = worker["current_job_id"]
                
                if wstatus == "busy":
                    worker_display.append(f"W{wid}:🔴Job{job_id}")
                else:
                    worker_display.append(f"W{wid}:🟢Idle")
            
            workers_str = " | ".join(worker_display)
            
            print(f"[{timestamp}] Queue: {queue_size:2d} | Busy: {busy} | Idle: {idle} | {workers_str}")
            
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"Monitor error: {e}")
            break


async def test_parallel_processing():
    """
    Test 1: Submit 10 PRs rapidly and watch workers process them in parallel.
    """
    print("\n" + "="*70)
    print("TEST 1: PARALLEL PROCESSING - Submitting 10 PRs")
    print("="*70)
    
    # Clean diff that should pass
    clean_diff = """diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,6 @@
+def new_function():
+    return "hello"
+
 def existing_function():
     return "world"
"""
    
    # Submit 10 PRs
    submit_tasks = []
    for i in range(1, 11):
        task = submit_pr(i, f"Test PR {i}", clean_diff)
        submit_tasks.append(task)
    
    print(f"\n⏳ Submitting 10 PRs simultaneously...")
    start = time.time()
    results = await asyncio.gather(*submit_tasks)
    submit_time = time.time() - start
    
    print(f"✅ All PRs submitted in {submit_time:.2f}s")
    
    for result in results:
        print(f"   Job {result['job_id']}: {result['status']}")
    
    # Monitor workers for 15 seconds
    print(f"\n⏳ Monitoring workers for 15 seconds...")
    await monitor_workers(15)
    
    # Check results
    print("\n" + "="*70)
    print("FINAL RESULTS")
    print("="*70)
    
    for result in results:
        job = await get_job(result['job_id'])
        status = job['status']
        latency = job.get('latency_ms', 'N/A')
        cache = "✅ CACHE HIT" if job.get('cache_hit') else "🔵 NEW REVIEW"
        
        print(f"Job {job['id']:2d} | PR {job['pr_number']:2d} | {status:15s} | {latency:>5}ms | {cache}")


async def test_queue_overflow():
    """
    Test 2: Submit 20 PRs with only 3 workers - demonstrate queuing.
    """
    print("\n\n" + "="*70)
    print("TEST 2: QUEUE OVERFLOW - Submitting 20 PRs (only 3 workers)")
    print("="*70)
    
    clean_diff = """diff --git a/test.py b/test.py
+def another_function():
+    return True
"""
    
    # Submit 20 PRs
    submit_tasks = []
    for i in range(100, 120):
        task = submit_pr(i, f"Batch PR {i}", clean_diff)
        submit_tasks.append(task)
    
    print(f"\n⏳ Submitting 20 PRs simultaneously...")
    results = await asyncio.gather(*submit_tasks)
    
    print(f"✅ All PRs submitted")
    
    # Immediately check queue size
    status = await get_status()
    print(f"\n📊 Immediate queue size: {status['queue_size']}")
    print(f"   Workers: {status['busy_workers']} busy, {status['idle_workers']} idle")
    
    # Monitor for 20 seconds
    print(f"\n⏳ Monitoring queue drain for 20 seconds...")
    await monitor_workers(20)


async def test_mixed_scenarios():
    """
    Test 3: Mix of scenarios - secrets, syntax errors, clean PRs.
    """
    print("\n\n" + "="*70)
    print("TEST 3: MIXED SCENARIOS - Secrets, Syntax Errors, Clean")
    print("="*70)
    
    scenarios = [
        (200, "Clean PR", """diff --git a/clean.py b/clean.py
+def clean():
+    return True
"""),
        (201, "PR with AWS Secret", """diff --git a/secret.py b/secret.py
+AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
"""),
        (202, "PR with Syntax Error", """diff --git a/broken.py b/broken.py
+def broken():
+    if True
+        print("missing colon")
"""),
        (203, "Another Clean PR", """diff --git a/good.py b/good.py
+def good():
+    return "works"
"""),
    ]
    
    # Submit all
    tasks = [submit_pr(num, title, diff) for num, title, diff in scenarios]
    print(f"\n⏳ Submitting {len(scenarios)} mixed PRs...")
    results = await asyncio.gather(*tasks)
    
    print(f"✅ All PRs submitted")
    
    # Wait for processing
    await asyncio.sleep(5)
    
    # Check results
    print("\n" + "="*70)
    print("RESULTS BY SCENARIO")
    print("="*70)
    
    for result in results:
        job = await get_job(result['job_id'])
        status = job['status']
        pr_title = job['title']
        
        icon = "✅" if status == "COMPLETED" else "❌"
        
        print(f"{icon} Job {job['id']:3d} | {pr_title:30s} | {status}")
        
        if status == "STATIC_FAILED":
            errors = job.get('static_result', {}).get('errors', [])
            for err in errors[:1]:  # Show first error
                print(f"      └─ {err}")


async def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("ASYNC WORKER QUEUE DEMONSTRATION")
    print("="*70)
    print("\nThis script demonstrates:")
    print("  1. Parallel processing with 3 async workers")
    print("  2. Queue management with overflow")
    print("  3. Mixed scenarios (clean, secrets, errors)")
    print("\nMake sure the backend is running: python start.py")
    print("="*70)
    
    # Verify backend is running
    try:
        status = await get_status()
        print(f"\n✅ Backend is running")
        print(f"   Workers: {status['total_workers']}")
        print(f"   Queue size: {status['queue_size']}")
    except Exception as e:
        print(f"\n❌ Cannot connect to backend at {API_BASE}")
        print(f"   Make sure to run: python start.py")
        return
    
    # Run tests
    await test_parallel_processing()
    await test_queue_overflow()
    await test_mixed_scenarios()
    
    print("\n" + "="*70)
    print("ALL TESTS COMPLETE")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
