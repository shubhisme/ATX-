"""
FastAPI backend orchestration with async worker pool.
Handles PR submission, job lifecycle, caching, and WebSocket updates.
Owned by Shubh.
"""
import asyncio
import time
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import db
from models import PRSubmitRequest, PRJobInsert, PRJobRow, PRStatus, WorkerStatus
from gates import run_gate
from context import gather_context
from agent import review_pr
from config import NUM_WORKERS, TOKEN_BUDGET


# ============================================================================
# Application State
# ============================================================================

job_queue: asyncio.Queue = None
worker_tasks: list[asyncio.Task] = []
worker_statuses: dict[int, WorkerStatus] = {}
websocket_connections: list[WebSocket] = []


# ============================================================================
# Lifecycle Management
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    global job_queue, worker_tasks, worker_statuses
    
    # Startup
    print("🚀 Initializing PR Verification Engine...")
    await db.init_db()
    print("✅ Database initialized")
    
    # Create async queue and workers
    job_queue = asyncio.Queue()
    
    for worker_id in range(NUM_WORKERS):
        worker_statuses[worker_id] = WorkerStatus(
            worker_id=worker_id,
            status="idle",
            current_job_id=None
        )
        task = asyncio.create_task(worker_loop(worker_id))
        worker_tasks.append(task)
    
    print(f"✅ Started {NUM_WORKERS} async workers")
    print(f"🎯 Ready to process PRs!")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down workers...")
    for task in worker_tasks:
        task.cancel()
    await asyncio.gather(*worker_tasks, return_exceptions=True)
    print("✅ Shutdown complete")


app = FastAPI(title="PR Verification Engine", lifespan=lifespan)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Worker Pool
# ============================================================================

async def worker_loop(worker_id: int):
    """
    Async worker that processes jobs from the queue.
    Follows the pipeline: Gate → Cache → Context → AI Review → Persist
    """
    print(f"🟢 Worker {worker_id} started and waiting for jobs")
    
    while True:
        try:
            # Wait for a job (blocks until job available)
            print(f"[Worker {worker_id}] Waiting for job...")
            job_id = await job_queue.get()
            
            # Update worker status
            worker_statuses[worker_id].status = "busy"
            worker_statuses[worker_id].current_job_id = job_id
            
            print(f"🔴 [Worker {worker_id}] Picked up job {job_id} (Queue size: {job_queue.qsize()})")
            
            # Process the job
            await process_job(job_id, worker_id)
            
            # Mark task done
            job_queue.task_done()
            
            # Reset worker status
            worker_statuses[worker_id].status = "idle"
            worker_statuses[worker_id].current_job_id = None
            
            print(f"🟢 [Worker {worker_id}] Completed job {job_id}, back to idle")
            
        except asyncio.CancelledError:
            print(f"⚠️  Worker {worker_id} cancelled")
            break
        except Exception as e:
            print(f"❌ Worker {worker_id} error: {e}")
            # Reset status and continue
            worker_statuses[worker_id].status = "idle"
            worker_statuses[worker_id].current_job_id = None
            job_queue.task_done()
            # Continue processing


async def process_job(job_id: int, worker_id: int):
    """
    Process a single PR job through the full pipeline.
    
    Pipeline:
    1. Deterministic gate
    2. Commit cache check
    3. Surgical context gathering
    4. Groq AI review
    5. Persistence and broadcasting
    """
    start_time = time.time()
    
    # Fetch job
    job = await db.get_job(job_id)
    if not job:
        return
    
    print(f"[Worker {worker_id}] Processing job {job_id} (PR #{job.pr_number})")
    
    # Mark as started
    started_at = datetime.utcnow().isoformat() + "Z"
    await db.update_job_status(job_id, PRStatus.AI_REVIEWING, started_at)
    await broadcast_job_update(job_id, "AI_REVIEWING")
    
    try:
        # ====================================================================
        # STEP 1: Deterministic Gate
        # ====================================================================
        gate_result = run_gate(job.diff, job.files)
        
        if not gate_result.passed:
            # Gate failed - reject without LLM call
            completed_at = datetime.utcnow().isoformat() + "Z"
            latency_ms = int((time.time() - start_time) * 1000)
            
            await db.complete_job(
                job_id=job_id,
                status=PRStatus.STATIC_FAILED,
                static_result={
                    "passed": False,
                    "errors": gate_result.errors,
                    "warnings": gate_result.warnings
                },
                completed_at=completed_at,
                latency_ms=latency_ms
            )
            
            await broadcast_job_update(job_id, "STATIC_FAILED")
            print(f"[Worker {worker_id}] Job {job_id} failed gate checks")
            return
        
        # ====================================================================
        # STEP 2: Commit Cache Check
        # ====================================================================
        cache_hit = await db.get_cache_hit(job.commit_sha)
        
        if cache_hit:
            # Reuse cached review
            completed_at = datetime.utcnow().isoformat() + "Z"
            latency_ms = int((time.time() - start_time) * 1000)
            
            await db.complete_job(
                job_id=job_id,
                status=PRStatus.COMPLETED,
                review=cache_hit.review,
                prompt_tokens=cache_hit.prompt_tokens,
                completion_tokens=cache_hit.completion_tokens,
                cost_usd=cache_hit.cost_usd,
                completed_at=completed_at,
                latency_ms=latency_ms,
                cache_hit=True
            )
            
            await broadcast_job_update(job_id, "COMPLETED")
            print(f"[Worker {worker_id}] Job {job_id} served from cache")
            return
        
        # ====================================================================
        # STEP 3: Surgical Context Gathering
        # ====================================================================
        context_result = gather_context(
            diff=job.diff,
            files=job.files,
            repo_path="sample_repo",
            token_budget=TOKEN_BUDGET
        )
        
        print(f"[Worker {worker_id}] Gathered {len(context_result.snippets)} context snippets")
        
        # ====================================================================
        # STEP 4: Groq AI Review
        # ====================================================================
        review_result = review_pr(
            diff=job.diff,
            context_snippets=context_result.snippets,
            title=job.title
        )
        
        print(f"[Worker {worker_id}] AI review completed: {len(review_result.findings)} findings")
        
        # ====================================================================
        # STEP 5: Persistence and Broadcasting
        # ====================================================================
        completed_at = datetime.utcnow().isoformat() + "Z"
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Build review dict
        review_dict = {
            "summary": review_result.summary,
            "findings": [
                {
                    "severity": f.severity,
                    "file": f.file,
                    "line": f.line,
                    "message": f.message,
                    "suggestion": f.suggestion
                }
                for f in review_result.findings
            ]
        }
        
        # Save to database
        await db.complete_job(
            job_id=job_id,
            status=PRStatus.COMPLETED,
            review=review_dict,
            prompt_tokens=review_result.prompt_tokens,
            completion_tokens=review_result.completion_tokens,
            cost_usd=review_result.cost_usd,
            completed_at=completed_at,
            latency_ms=latency_ms,
            cache_hit=False
        )
        
        # Cache for future use
        from models import CacheInsert
        await db.insert_cache(CacheInsert(
            commit_sha=job.commit_sha,
            review=review_dict,
            prompt_tokens=review_result.prompt_tokens,
            completion_tokens=review_result.completion_tokens,
            cost_usd=review_result.cost_usd,
            created_at=completed_at
        ))
        
        await broadcast_job_update(job_id, "COMPLETED")
        print(f"[Worker {worker_id}] Job {job_id} completed in {latency_ms}ms")
        
    except Exception as e:
        print(f"[Worker {worker_id}] Job {job_id} failed with error: {e}")
        # Could add a FAILED status here if needed


# ============================================================================
# WebSocket Broadcasting
# ============================================================================

async def broadcast_job_update(job_id: int, status: str):
    """Broadcast job status update to all connected WebSocket clients."""
    message = {
        "type": "job_update",
        "job_id": job_id,
        "status": status,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    
    # Send to all connected clients
    disconnected = []
    for ws in websocket_connections:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
    
    # Clean up disconnected clients
    for ws in disconnected:
        websocket_connections.remove(ws)


# ============================================================================
# API Endpoints
# ============================================================================

class SubmitResponse(BaseModel):
    job_id: int
    status: str
    message: str


@app.post("/submit", response_model=SubmitResponse)
async def submit_pr(request: PRSubmitRequest):
    """
    Submit a PR for review. Returns immediately with job ID.
    Processing happens asynchronously in the worker pool.
    """
    # Create job record
    queued_at = datetime.utcnow().isoformat() + "Z"
    
    job_insert = PRJobInsert(
        pr_number=request.pr_number,
        title=request.title,
        commit_sha=request.commit_sha,
        diff=request.diff,
        files=request.files,
        queued_at=queued_at
    )
    
    job_id = await db.insert_job(job_insert)
    
    # Supersede old jobs for this PR
    await db.supersede_old_jobs(request.pr_number, request.commit_sha)
    
    # Add to queue
    await job_queue.put(job_id)
    
    queue_size = job_queue.qsize()
    busy_workers = sum(1 for ws in worker_statuses.values() if ws.status == "busy")
    
    print(f"✨ PR #{request.pr_number} submitted as job {job_id} | Queue: {queue_size} | Busy workers: {busy_workers}/{NUM_WORKERS}")
    
    return SubmitResponse(
        job_id=job_id,
        status="QUEUED",
        message=f"PR submitted successfully. Job ID: {job_id}"
    )


@app.get("/jobs")
async def list_jobs(limit: int = 50):
    """List all jobs with their current status."""
    jobs = await db.get_all_jobs(limit)
    
    return {
        "jobs": [
            {
                "id": job.id,
                "job_id": f"job-{job.id:03d}",
                "pr_number": job.pr_number,
                "title": job.title,
                "commit_sha": job.commit_sha,
                "status": job.status.value,
                "queued_at": job.queued_at,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
                "latency_ms": job.latency_ms,
                "cache_hit": job.cache_hit,
                "prompt_tokens": job.prompt_tokens,
                "completion_tokens": job.completion_tokens,
                "tokens_in": job.prompt_tokens,
                "tokens_out": job.completion_tokens,
                "cost_usd": job.cost_usd,
                "diff": job.diff,
                "diff_content": job.diff,
                "static_result": job.static_result,
                "review": job.review,
            }
            for job in jobs
        ],
        "total": len(jobs)
    }


@app.get("/jobs/{job_id}")
async def get_job_detail(job_id: str):
    """Get detailed information about a specific job (supports 1, '1', 'job-001')."""
    raw_str = job_id.replace("job-", "").lstrip("0") or "0"
    numeric_id = int(raw_str) if raw_str.isdigit() else None
    job = await db.get_job(numeric_id) if numeric_id is not None else None
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "id": job.id,
        "job_id": f"job-{job.id:03d}",
        "pr_number": job.pr_number,
        "title": job.title,
        "commit_sha": job.commit_sha,
        "status": job.status.value,
        "files": job.files,
        "diff": job.diff,
        "diff_content": job.diff,
        "static_result": job.static_result,
        "review": job.review,
        "prompt_tokens": job.prompt_tokens,
        "completion_tokens": job.completion_tokens,
        "tokens_in": job.prompt_tokens,
        "tokens_out": job.completion_tokens,
        "cost_usd": job.cost_usd,
        "queued_at": job.queued_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "latency_ms": job.latency_ms,
        "cache_hit": job.cache_hit,
    }


@app.get("/status")
async def get_system_status():
    """Get current system status including queue and worker information."""
    busy_workers = sum(1 for ws in worker_statuses.values() if ws.status == "busy")
    idle_workers = sum(1 for ws in worker_statuses.values() if ws.status == "idle")
    
    return {
        "queue_size": job_queue.qsize(),
        "total_workers": NUM_WORKERS,
        "busy_workers": busy_workers,
        "idle_workers": idle_workers,
        "workers": [
            {
                "worker_id": ws.worker_id,
                "status": ws.status,
                "current_job_id": ws.current_job_id
            }
            for ws in worker_statuses.values()
        ],
        "websocket_connections": len(websocket_connections),
        "worker_tasks_alive": sum(1 for task in worker_tasks if not task.done())
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live job updates."""
    await websocket.accept()
    websocket_connections.append(websocket)
    
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_connections.remove(websocket)


@app.get("/")
async def root():
    """API root - health check."""
    return {
        "service": "PR Verification Engine",
        "status": "running",
        "workers": NUM_WORKERS
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
