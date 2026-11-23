"""
PR Simulator - generates sample PRs for testing the pipeline.
Can submit single PRs or batch submissions to test concurrency.
"""
import asyncio
import httpx
from datetime import datetime


# Sample diffs for testing different scenarios
SAMPLE_DIFFS = {
    "clean": """
diff --git a/sample_repo/utils.py b/sample_repo/utils.py
index 1234567..abcdefg 100644
--- a/sample_repo/utils.py
+++ b/sample_repo/utils.py
@@ -10,6 +10,10 @@ def generate_uuid() -> str:
     import uuid
     return str(uuid.uuid4())
 
+def format_timestamp(ts: str) -> str:
+    \"\"\"Format ISO timestamp for display.\"\"\"
+    return datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M:%S")
+
 def sanitize_input(value: str) -> str:
     \"\"\"Remove dangerous characters from user input.\"\"\"
     return value.strip()
""",
    
    "with_secret": """
diff --git a/sample_repo/config.py b/sample_repo/config.py
index 1234567..abcdefg 100644
--- a/sample_repo/config.py
+++ b/sample_repo/config.py
@@ -5,6 +5,7 @@ import os
 DATABASE_URL = os.getenv("DATABASE_URL")
 DEBUG = True
+API_KEY = "AKIAIOSFODNN7EXAMPLE"
 
 def get_config():
     return {
""",
    
    "syntax_error": """
diff --git a/sample_repo/broken.py b/sample_repo/broken.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/sample_repo/broken.py
@@ -0,0 +1,5 @@
+def broken_function():
+    if True
+        print("Missing colon")
+    return None
+
""",
    
    "auth_improvement": """
diff --git a/sample_repo/auth.py b/sample_repo/auth.py
index 1234567..abcdefg 100644
--- a/sample_repo/auth.py
+++ b/sample_repo/auth.py
@@ -15,7 +15,10 @@ def hash_password(password: str) -> str:
     Returns a 'salt:hash' string safe to store in the database.
     \"\"\"
     salt = os.urandom(16).hex()
-    pw_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
+    # Use PBKDF2 for better security
+    pw_hash = hashlib.pbkdf2_hmac(
+        'sha256', password.encode(), salt.encode(), 100000
+    ).hex()
     return f"{salt}:{pw_hash}"
 
 def authenticate_user(username: str, password: str) -> dict | None:
"""
}


async def submit_pr(
    pr_number: int,
    title: str,
    diff_type: str = "clean",
    api_url: str = "http://localhost:8000"
):
    """Submit a single PR to the backend."""
    commit_sha = f"{pr_number:040d}"  # Fake 40-char SHA
    
    payload = {
        "pr_number": pr_number,
        "title": title,
        "commit_sha": commit_sha,
        "diff": SAMPLE_DIFFS.get(diff_type, SAMPLE_DIFFS["clean"]),
        "files": ["sample_repo/utils.py"]
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{api_url}/submit", json=payload, timeout=10.0)
        return response.json()


async def submit_batch(count: int = 20, api_url: str = "http://localhost:8000"):
    """Submit a batch of PRs to test concurrent processing."""
    print(f"📦 Submitting batch of {count} PRs...")
    
    tasks = []
    for i in range(1, count + 1):
        # Mix different types
        if i % 7 == 0:
            diff_type = "with_secret"
        elif i % 11 == 0:
            diff_type = "syntax_error"
        elif i % 5 == 0:
            diff_type = "auth_improvement"
        else:
            diff_type = "clean"
        
        title = f"PR {i}: Test pull request"
        task = submit_pr(i, title, diff_type, api_url)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    print(f"✅ Submitted {len(results)} PRs")
    for i, result in enumerate(results, 1):
        if isinstance(result, dict):
            print(f"  PR {i}: Job ID {result.get('job_id')}")
        else:
            print(f"  PR {i}: Error - {result}")
    
    return results


async def submit_duplicate_commits():
    """Submit PRs with duplicate commits to test caching."""
    print("🔄 Testing commit cache with duplicate SHAs...")
    
    # Same commit SHA
    commit_sha = "a" * 40
    
    payload_1 = {
        "pr_number": 101,
        "title": "First PR with commit A",
        "commit_sha": commit_sha,
        "diff": SAMPLE_DIFFS["clean"],
        "files": ["sample_repo/utils.py"]
    }
    
    payload_2 = {
        "pr_number": 102,
        "title": "Second PR with same commit A (should cache hit)",
        "commit_sha": commit_sha,
        "diff": SAMPLE_DIFFS["clean"],
        "files": ["sample_repo/utils.py"]
    }
    
    async with httpx.AsyncClient() as client:
        # Submit first PR
        r1 = await client.post("http://localhost:8000/submit", json=payload_1, timeout=10.0)
        print(f"✅ Submitted PR 101: {r1.json()}")
        
        # Wait for completion
        await asyncio.sleep(5)
        
        # Submit duplicate
        r2 = await client.post("http://localhost:8000/submit", json=payload_2, timeout=10.0)
        print(f"✅ Submitted PR 102: {r2.json()}")
        
        # Wait and check results
        await asyncio.sleep(2)
        
        job1 = await client.get(f"http://localhost:8000/jobs/{r1.json()['job_id']}")
        job2 = await client.get(f"http://localhost:8000/jobs/{r2.json()['job_id']}")
        
        print(f"\nJob 1 cache_hit: {job1.json()['cache_hit']}")
        print(f"Job 2 cache_hit: {job2.json()['cache_hit']} (should be True)")


async def test_supersession():
    """Test that newer commits supersede older ones for the same PR."""
    print("🔄 Testing job supersession...")
    
    pr_number = 999
    
    # Submit first commit
    payload_1 = {
        "pr_number": pr_number,
        "title": "PR 999 - First commit",
        "commit_sha": "b" * 40,
        "diff": SAMPLE_DIFFS["clean"],
        "files": ["sample_repo/utils.py"]
    }
    
    # Submit second commit (should supersede first)
    payload_2 = {
        "pr_number": pr_number,
        "title": "PR 999 - Updated commit",
        "commit_sha": "c" * 40,
        "diff": SAMPLE_DIFFS["auth_improvement"],
        "files": ["sample_repo/auth.py"]
    }
    
    async with httpx.AsyncClient() as client:
        r1 = await client.post("http://localhost:8000/submit", json=payload_1, timeout=10.0)
        print(f"✅ Submitted first commit: {r1.json()}")
        
        # Immediately submit newer commit
        r2 = await client.post("http://localhost:8000/submit", json=payload_2, timeout=10.0)
        print(f"✅ Submitted newer commit: {r2.json()}")
        
        # Check both jobs
        await asyncio.sleep(3)
        
        job1 = await client.get(f"http://localhost:8000/jobs/{r1.json()['job_id']}")
        job2 = await client.get(f"http://localhost:8000/jobs/{r2.json()['job_id']}")
        
        print(f"\nFirst job status: {job1.json()['status']} (may be SUPERSEDED)")
        print(f"Second job status: {job2.json()['status']}")


# ============================================================================
# CLI Interface
# ============================================================================

async def main():
    """Interactive simulator CLI."""
    import sys
    
    if len(sys.argv) < 2:
        print("""
PR Simulator Usage:

  python simulator.py single <pr_number> [clean|with_secret|syntax_error|auth_improvement]
  python simulator.py batch [count]
  python simulator.py cache
  python simulator.py supersede

Examples:
  python simulator.py single 1
  python simulator.py single 2 with_secret
  python simulator.py batch 20
  python simulator.py cache
  python simulator.py supersede
        """)
        return
    
    command = sys.argv[1]
    
    if command == "single":
        pr_num = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        diff_type = sys.argv[3] if len(sys.argv) > 3 else "clean"
        result = await submit_pr(pr_num, f"Test PR {pr_num}", diff_type)
        print(f"✅ Submitted: {result}")
    
    elif command == "batch":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        await submit_batch(count)
    
    elif command == "cache":
        await submit_duplicate_commits()
    
    elif command == "supersede":
        await test_supersession()
    
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    asyncio.run(main())
