"""
Visual representation of the async queue architecture.
"""


def print_architecture():
    """Print ASCII art showing the architecture."""
    
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    ASYNC PARALLEL QUEUE ARCHITECTURE                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

                        PR SUBMISSIONS (concurrent)
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
                  PR #1          PR #2          PR #3  ...  PR #N
                    │              │              │              │
                    └──────────────┴──────────────┴──────────────┘
                                   │
                                   ▼
                        ╔══════════════════════╗
                        ║   FastAPI Endpoint   ║
                        ║    POST /submit      ║
                        ╚══════════════════════╝
                                   │
                        ┌──────────┴──────────┐
                        │  Insert to SQLite   │
                        │   (save job state)  │
                        └──────────┬──────────┘
                                   │
                                   ▼
                        ╔══════════════════════╗
                        ║  asyncio.Queue()     ║
                        ║  job_queue.put(id)   ║
                        ║                      ║
                        ║  [Job1, Job2, Job3,  ║
                        ║   Job4, Job5, ...]   ║
                        ╚══════════════════════╝
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
     ┏━━━━━━━━━━━━━┓      ┏━━━━━━━━━━━━━┓      ┏━━━━━━━━━━━━━┓
     ┃  WORKER 0   ┃      ┃  WORKER 1   ┃      ┃  WORKER 2   ┃
     ┃             ┃      ┃             ┃      ┃             ┃
     ┃ await get() ┃      ┃ await get() ┃      ┃ await get() ┃
     ┗━━━━━━┯━━━━━━┛      ┗━━━━━━┯━━━━━━┛      ┗━━━━━━┯━━━━━━┛
            │                     │                     │
            │                     │                     │
     (Processing)          (Processing)          (Processing)
     Job #1 ▶              Job #2 ▶              Job #3 ▶
            │                     │                     │
            ▼                     ▼                     ▼
     ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
     │ 1. Gate      │      │ 1. Gate      │      │ 1. Gate      │
     │ 2. Cache     │      │ 2. Cache     │      │ 2. Cache     │
     │ 3. Context   │      │ 3. Context   │      │ 3. Context   │
     │ 4. AI Review │      │ 4. AI Review │      │ 4. AI Review │
     │ 5. Persist   │      │ 5. Persist   │      │ 5. Persist   │
     └──────┬───────┘      └──────┬───────┘      └──────┬───────┘
            │                     │                     │
            └──────────────┬──────┴──────────────┬──────┘
                           │                     │
                           ▼                     ▼
                    ┌──────────────┐    ┌──────────────┐
                    │   SQLite     │    │  WebSocket   │
                    │   (results)  │    │  (broadcast) │
                    └──────────────┘    └──────────────┘


╔══════════════════════════════════════════════════════════════════════════════╗
║                              KEY FEATURES                                    ║
╚══════════════════════════════════════════════════════════════════════════════╝

  🚀 NON-BLOCKING SUBMISSION
     • POST /submit returns immediately with job_id
     • No waiting for AI review to complete
     • Client can submit many PRs rapidly

  ⚡ PARALLEL PROCESSING
     • 3 workers process jobs concurrently
     • Each worker is an async coroutine
     • True parallelism within single process

  📋 AUTOMATIC QUEUE MANAGEMENT
     • asyncio.Queue handles distribution
     • Workers block on queue.get() until job available
     • No busy-waiting, no polling

  🔄 CONTINUOUS OPERATION
     • Workers run in infinite loop
     • Pick up jobs as they arrive
     • Return to idle when queue is empty

  📊 REAL-TIME MONITORING
     • Track worker status (busy/idle)
     • Monitor queue size
     • WebSocket updates to clients


╔══════════════════════════════════════════════════════════════════════════════╗
║                           EXAMPLE TIMELINE                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝

  t = 0.00s   Submit 10 PRs simultaneously
              → All 10 jobs queued in < 100ms

  t = 0.10s   Worker 0 starts processing Job #1
              Worker 1 starts processing Job #2
              Worker 2 starts processing Job #3
              (Jobs 4-10 waiting in queue)

  t = 2.50s   Worker 0 completes Job #1
              → Immediately picks up Job #4

  t = 3.00s   Worker 1 completes Job #2
              → Immediately picks up Job #5

  t = 3.20s   Worker 2 completes Job #3
              → Immediately picks up Job #6

  t = 5.50s   Worker 0 completes Job #4
              → Immediately picks up Job #7

  ...and so on until all jobs processed


╔══════════════════════════════════════════════════════════════════════════════╗
║                         CONFIGURATION                                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

  File: backend/config.py

      NUM_WORKERS = 3    # Can be changed to 5, 10, etc.

  Environment variable:

      NUM_WORKERS=5 python start.py


╔══════════════════════════════════════════════════════════════════════════════╗
║                           MONITORING                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

  API Endpoint:
      GET http://localhost:8000/status

  Real-time Monitor:
      python monitor_queue.py

  Backend Logs:
      ✨ PR #1 submitted as job 1 | Queue: 7 | Busy workers: 3/3
      🔴 [Worker 0] Picked up job 1 (Queue size: 6)
      🟢 [Worker 0] Completed job 1, back to idle


╔══════════════════════════════════════════════════════════════════════════════╗
║                         TEST THE SYSTEM                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

  Terminal 1 - Start backend:
      python start.py

  Terminal 2 - Monitor workers:
      python monitor_queue.py

  Terminal 3 - Submit PRs:
      python demo_parallel.py

  You'll see workers processing jobs in parallel! 🚀

""")


if __name__ == "__main__":
    print_architecture()
