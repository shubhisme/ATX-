"""
Simple demonstration of parallel queue processing.
Shows how 3 workers process jobs concurrently from the async queue.
"""
import asyncio
import httpx
import time


API_BASE = "http://localhost:8000"


async def submit_simple_pr(pr_number: int):
    """Submit a simple PR."""
    payload = {
        "pr_number": pr_number,
        "title": f"PR #{pr_number}",
        "commit_sha": f"{pr_number:040d}",
        "diff": f"diff --git a/test.py b/test.py\n+# Change {pr_number}",
        "files": ["test.py"]
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{API_BASE}/submit", json=payload, timeout=10.0)
        return response.json()


async def main():
    """
    Submit 10 PRs and watch workers process them in parallel.
    """
    
    print("\n" + "="*70)
    print(" "*15 + "PARALLEL QUEUE DEMONSTRATION")
    print("="*70)
    
    print("\nBackend configuration:")
    print("  • 3 async workers")
    print("  • asyncio.Queue for job distribution")
    print("  • Workers process jobs concurrently")
    
    print("\nDemo: Submitting 10 PRs rapidly...")
    print("-"*70)
    
    # Submit 10 PRs simultaneously
    start_time = time.time()
    
    tasks = [submit_simple_pr(i) for i in range(1, 11)]
    results = await asyncio.gather(*tasks)
    
    submission_time = time.time() - start_time
    
    print(f"\n✅ Submitted 10 PRs in {submission_time:.3f} seconds")
    print(f"\nJob IDs created:")
    for result in results:
        print(f"  • Job {result['job_id']}: {result['status']}")
    
    print("\n" + "="*70)
    print("What's happening in the backend:")
    print("="*70)
    print("""
  1. All 10 PRs submitted almost instantly (async submission)
  2. Jobs queued in asyncio.Queue
  3. 3 workers pick up jobs concurrently:
     - Worker 0: Processes job 1
     - Worker 1: Processes job 2  
     - Worker 2: Processes job 3
     (all at the same time!)
  
  4. As each worker completes:
     - Worker 0 finishes → picks up job 4
     - Worker 1 finishes → picks up job 5
     - Worker 2 finishes → picks up job 6
     (continues until queue is empty)
  
  5. Jobs 7, 8, 9, 10 wait in queue until workers are free
    """)
    
    print("="*70)
    print("To monitor in real-time, run in another terminal:")
    print("  python monitor_queue.py")
    print("="*70)
    
    print("\n✨ Check backend logs to see worker activity!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except httpx.ConnectError:
        print("\n❌ Cannot connect to backend")
        print("Make sure to start it first: python start.py")
    except KeyboardInterrupt:
        print("\n👋 Cancelled")
