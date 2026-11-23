# Requirements Document

## Introduction

The PR Verification Engine is a high-throughput platform for reviewing Git pull requests. It routes every PR through a zero-cost deterministic gate before invoking an LLM, uses commit-SHA caching to avoid re-reviewing identical code, and surfaces live telemetry in a Next.js UI. The system runs as a continuous background service with an async worker pool — not a single-PR script.

## Requirements

### 1. PR Submission and Lifecycle Management

#### 1.1 Single PR Submission

The system shall accept a single PR via `POST /api/pr/submit` with fields `pr_number`, `title`, `commit_sha` (40-char hex), `diff` (unified diff string, max 100,000 characters), and `files` (list of changed file paths).

**Acceptance Criteria**:
- Given a valid PR submission, the system creates a `pr_jobs` row with status `QUEUED` and returns `202 {"job_id": int}` before the review is complete.
- Given a `diff` exceeding 100,000 characters, the system returns `422` without creating a job or touching the queue.
- Given a malformed or missing required field, the system returns `400` without creating a job.
- Given a valid submission, the returned `job_id` is immediately visible via `GET /api/pr/:id`.

#### 1.2 Batch PR Submission

The system shall accept a batch of up to 20 PRs via `POST /api/pr/batch` and enqueue all valid jobs atomically.

**Acceptance Criteria**:
- Given a batch of 1–20 valid PRs, the system returns `202 {"jobs": [...]}` with one entry per submitted PR.
- Given a batch exceeding 20 items, the system returns `422 {"error": "batch_size_exceeded", "max": 20, "received": N}` without creating any jobs.
- Given multiple PRs in the same batch sharing the same `pr_number`, all but the last (by submission order) are marked `SUPERSEDED` immediately.

#### 1.3 PR Lifecycle States

Every PR job shall progress through a defined set of states: `QUEUED` → (`STATIC_FAILED` | `AI_REVIEWING`) → (`COMPLETED` | `SUPERSEDED`).

**Acceptance Criteria**:
- Given a job is created, its initial status is `QUEUED`.
- Given a job fails the static gate, its status transitions to `STATIC_FAILED` and no further transitions occur.
- Given a job passes the static gate, its status transitions to `AI_REVIEWING` before the LLM is called.
- Given a job completes LLM review, its status transitions to `COMPLETED`.
- Given a newer job arrives for the same `pr_number` while the prior job is still `QUEUED`, the prior job transitions to `SUPERSEDED`.
- Given a job is in a terminal state (`STATIC_FAILED`, `COMPLETED`, `SUPERSEDED`), its status does not change further.

#### 1.4 Job Cancellation

The system shall support cancelling a queued job via `DELETE /api/pr/:id`.

**Acceptance Criteria**:
- Given a job in `QUEUED` status, `DELETE /api/pr/:id` transitions it to `SUPERSEDED` and returns `200 {"cancelled": true}`.
- Given a job in `AI_REVIEWING` or any terminal status, `DELETE /api/pr/:id` returns `409 {"error": "already_terminal"}` without changing the job.
- Given a non-existent `job_id`, `DELETE /api/pr/:id` returns `404`.

### 2. Worker Pool and Queue Management

#### 2.1 Async Worker Pool

The system shall process PR jobs using a `ThreadPoolExecutor` with exactly 3 worker threads backed by a `queue.Queue`.

**Acceptance Criteria**:
- Given the service starts, exactly 3 worker threads are running and accepting jobs from the queue.
- Given 3 jobs are in progress simultaneously, a 4th enqueued job waits in the queue until a worker becomes available.
- Given a worker thread crashes on an unhandled exception, it is replaced by the pool before accepting further jobs — OR the exception is caught per-job and the worker continues processing subsequent jobs.

#### 2.2 Supersede Logic

When a new job for `pr_number` N is enqueued, any existing `QUEUED` job for the same `pr_number` shall be marked `SUPERSEDED`.

**Acceptance Criteria**:
- At any point in time, at most one job per `pr_number` is in `{QUEUED, AI_REVIEWING}` state.
- Given two rapid submissions for the same `pr_number`, only the most recent proceeds to review; the earlier is `SUPERSEDED`.
- Given a job for `pr_number` N is in `AI_REVIEWING`, a new submission for N is enqueued normally (the in-progress job is not interrupted).

#### 2.3 Exponential Backoff on Rate Limits

Workers shall retry LLM calls that receive HTTP 429 (rate limit) with exponential backoff.

**Acceptance Criteria**:
- Given a 429 response on attempt K (0-indexed), the worker sleeps `min(2^K, 32)` seconds before retrying.
- Given 5 consecutive 429 responses, the worker stops retrying and transitions the job to `STATIC_FAILED` with `static_result.error = "rate_limit_exhausted"`.
- Given a non-429 HTTP error from the LLM, the worker does not retry and transitions the job to `STATIC_FAILED` immediately.

### 3. Deterministic Static Gate

#### 3.1 Gate Execution Time

The static gate shall complete in under 100 ms for any input diff.

**Acceptance Criteria**:
- Given any valid diff string, `run_static_gates(diff)` returns a `GateResult` with `duration_ms < 100`.
- Given the gate passes, the returned `GateResult.passed` is `True` and `GateResult.checks` contains one `CheckResult` per registered check, all with `passed=True`.
- Given the gate fails, `GateResult.passed` is `False` and at least one `CheckResult` in `GateResult.checks` has `passed=False`.

#### 3.2 Secret Scanning

The gate shall detect credential patterns in added lines (lines beginning with `+`) of the diff.

**Acceptance Criteria**:
- Given a diff with a line starting with `+` containing a string matching `AKIA[0-9A-Z]{16}`, the gate returns `passed=False` with finding name `AWS_ACCESS_KEY`.
- Given a diff with a JWT token (`eyJ...`) on an added line, the gate returns `passed=False` with finding name `JWT_TOKEN`.
- Given a diff with a generic API key pattern on an added line, the gate returns `passed=False` with finding name `API_KEY_GENERIC`.
- Given a diff with a `-----BEGIN PRIVATE KEY-----` header on an added line, the gate returns `passed=False` with finding name `PRIVATE_KEY`.
- Given a diff where matching patterns appear only on context lines (no `+` prefix) or removed lines (`-` prefix), the gate returns `passed=True`.

#### 3.3 Syntax Checking

The gate shall parse added Python code blocks from the diff using `ast.parse`.

**Acceptance Criteria**:
- Given a diff where the added lines (stripped of `+`) form valid Python syntax, the syntax check passes.
- Given a diff where added lines contain a Python `SyntaxError`, the gate returns `passed=False` with a finding describing the error location and message.
- Given a diff containing non-Python files or empty added-line sections, the syntax check passes without error.

### 4. Commit-SHA Caching

#### 4.1 Cache Lookup Before LLM

Before invoking any LLM call, the worker shall check `review_cache` for the job's `commit_sha`.

**Acceptance Criteria**:
- Given a `commit_sha` present in `review_cache`, the job is marked `COMPLETED` with `cache_hit=True`, `cost_usd=0.0`, and the cached `review` data — without invoking the LLM.
- Given a `commit_sha` absent from `review_cache`, the pipeline proceeds to the static gate.

#### 4.2 Cache Write After Review

After a successful LLM review, the result shall be written to `review_cache` keyed by `commit_sha`.

**Acceptance Criteria**:
- Given a job completes with `cache_hit=False`, a row is inserted into `review_cache` with the `commit_sha`, review JSON, token counts, `cost_usd`, and `created_at` timestamp.
- Given the same `commit_sha` is submitted again after a successful review, the second job has `cache_hit=True` and `cost_usd=0.0`.
- Given two concurrent workers receive jobs with the same `commit_sha` simultaneously, only one LLM call is made and the result is cached for both.

### 5. Context Gathering Pipeline

#### 5.1 Dependency Resolution

The pipeline shall resolve direct imports from changed files, returning at most 3 local dependency file paths.

**Acceptance Criteria**:
- Given a changed file importing `from utils import helper`, and `sample_repo/utils.py` exists, `resolve_dependencies` returns `sample_repo/utils.py` in its result.
- Given imports that resolve to stdlib or third-party packages (not present in `sample_repo/`), those imports are silently skipped.
- Given resolution would yield more than 3 local dependencies, the result is capped at 3 (first resolved wins).
- Given a changed file that cannot be parsed (binary or syntax error), it is skipped without raising an exception.

#### 5.2 Symbol Context Extraction

The pipeline shall extract function and class definitions referenced in the diff from dependency files, capping each at 60 lines.

**Acceptance Criteria**:
- Given a dependency file containing a function `validate_card` and that name appears in the diff, `read_symbol_context` returns a `SymbolContext` with `symbol="validate_card"` and `source_lines` containing the function body.
- Given a function longer than 60 lines, `source_lines` contains exactly the first 60 lines.
- Given a symbol name that does not appear in the file, no `SymbolContext` is returned for that symbol.
- Given a file that cannot be opened or parsed, `read_symbol_context` raises an `OSError` or `SyntaxError` (the caller handles it).

#### 5.3 Prompt Token Budget

The assembled review prompt shall not exceed 4000 tokens (estimated as `len(prompt) // 4`).

**Acceptance Criteria**:
- Given a diff and symbol contexts where the full assembly would exceed 4000 tokens, symbol contexts are truncated (removed from the prompt) until the budget is met; the diff is never truncated.
- Given a diff and symbol contexts that together fit within 4000 tokens, all context is included in the prompt.
- Given `build_context_prompt` is called with any valid inputs satisfying preconditions, the returned string always satisfies `len(result) // 4 < 4000`.

### 6. LLM Review via Groq

#### 6.1 Structured Review Output

The Groq client shall request and parse a structured JSON review response from `llama-3.3-70b-versatile`.

**Acceptance Criteria**:
- Given a successful LLM response, `GroqClient.review()` returns an `LLMReview` with `summary` (string), `findings` (list of `Finding`), `severity` ("low" | "medium" | "high" | "critical"), `prompt_tokens`, `completion_tokens`, and `cost_usd`.
- Given each `Finding`, it contains `file` (string), `line` (int or null), `severity` (string), and `message` (string).
- Given the LLM returns a response that cannot be parsed as JSON, the client falls back to `LLMReview(summary=raw_text, findings=[], severity="low", ...)` rather than raising an error.

#### 6.2 Token Cost Tracking

The client shall compute `cost_usd` from token counts using the per-model pricing for `llama-3.3-70b-versatile`.

**Acceptance Criteria**:
- Given `prompt_tokens=P` and `completion_tokens=C`, `cost_usd = P * INPUT_RATE + C * OUTPUT_RATE` where rates match the Groq pricing for the configured model.
- Given a cache-hit job, `cost_usd` stored in `pr_jobs` is `0.0` regardless of the cached review's original cost.

### 7. Real-Time SSE Stream

#### 7.1 State Change Events

The system shall emit a Server-Sent Event whenever a job transitions to a new status.

**Acceptance Criteria**:
- Given a connected SSE client (`GET /api/stream`), it receives an event for every status transition of every job, with payload `{"job_id": int, "status": string, "ts": ISO-8601}`.
- Given a client connects mid-stream, it receives future events but not past events.
- Given no events occur for 15 seconds, the server emits a keepalive comment (`: keepalive\n\n`) to maintain the connection.
- Given a client disconnects, its subscriber queue is removed without affecting other clients.

#### 7.2 Queue Status Endpoint

The system shall provide a point-in-time snapshot of all jobs and workers via `GET /api/queue/status`.

**Acceptance Criteria**:
- Given the endpoint is called, it returns `200` with `workers` (list of `WorkerStatus`), `jobs` (list of all `PRJob`), and `aggregate` (totals).
- Given the aggregate, it includes `total_jobs`, `completed`, `static_failed`, `cache_hits`, `total_cost_usd`, and `avg_latency_ms`.

### 8. SQLite Persistence

#### 8.1 Schema Initialization

The database schema shall be created automatically on first run if tables do not exist.

**Acceptance Criteria**:
- Given the Flask app starts with no existing database file, `db.init_schema()` creates both `pr_jobs` and `review_cache` tables with the specified columns and indices.
- Given the Flask app starts with an existing database file, `init_schema()` is idempotent and does not destroy existing data.

#### 8.2 Thread Safety

All database operations shall be safe for concurrent access from multiple worker threads.

**Acceptance Criteria**:
- Given 3 workers simultaneously writing to `pr_jobs`, no data corruption or `sqlite3.OperationalError` (database locked) occurs.
- Given a read and a write occur concurrently, the read returns a consistent snapshot (not partial write state).

### 9. Frontend — Queue Monitor

#### 9.1 Live Queue Table

The queue monitor page (`/`) shall display all PR jobs with live status updates via SSE.

**Acceptance Criteria**:
- Given the page loads, it shows a table with one row per PR job, including `pr_number`, `title`, `status`, `cache_hit` badge, `latency_ms`, and `cost_usd`.
- Given a job transitions status (via SSE), the row updates within one second without a page reload.
- Given a worker becomes busy or idle, the worker concurrency panel updates accordingly.

#### 9.2 PR Detail View

The PR detail page (`/pr/[id]`) shall display the full diff with inline AI review findings.

**Acceptance Criteria**:
- Given the page loads for a `COMPLETED` job, it shows the unified diff with review findings overlaid at relevant line numbers.
- Given the page loads for a `STATIC_FAILED` job, it shows the static gate findings (which check failed and what was detected).
- Given the page loads for a job in `QUEUED` or `AI_REVIEWING`, it shows the current status and auto-refreshes via SSE until a terminal state is reached.

#### 9.3 Telemetry Display

Each job shall display per-PR telemetry: latency ms, prompt tokens, completion tokens, estimated cost, and cache hit status.

**Acceptance Criteria**:
- Given a `COMPLETED` job with `cache_hit=False`, the telemetry badge shows prompt tokens, completion tokens, cost in USD, and latency ms.
- Given a `COMPLETED` job with `cache_hit=True`, the telemetry badge shows a "Cache Hit" indicator and `cost_usd=0.00`.
- Given aggregate stats are displayed, they show total jobs, total cost USD, cache hit rate (%), and average latency ms.

### 10. Frontend — Batch Simulator

#### 10.1 Batch Submission UI

The batch simulator shall allow submitting 1 to 20 simulated PRs with one click.

**Acceptance Criteria**:
- Given the user selects a count between 1 and 20 and clicks "Submit Batch", the UI calls `POST /api/pr/batch` with the specified number of synthetic PR payloads.
- Given the batch is submitted, the queue table updates to show the new jobs with `QUEUED` status immediately.
- Given the batch includes PRs with the same `pr_number` as an existing queued job, the UI reflects the `SUPERSEDED` status for the older job.

## Glossary

| Term | Definition |
|---|---|
| **PR Job** | A single pull request submitted for review, tracked as a row in `pr_jobs` with a unique `job_id`. |
| **commit_sha** | A 40-character hexadecimal Git commit hash that uniquely identifies the state of code being reviewed. |
| **Static Gate** | The deterministic, zero-LLM-cost check that runs regex secret scanning and AST syntax validation on the diff before any worker queue processing. |
| **Cache Hit** | When a job's `commit_sha` already exists in `review_cache`, the stored review is returned without invoking the LLM and `cost_usd` is recorded as 0. |
| **Supersede** | The act of marking an older `QUEUED` job for the same `pr_number` as `SUPERSEDED` when a newer commit arrives, preventing wasted LLM spend on stale code. |
| **Worker** | One of the 3 threads in the `ThreadPoolExecutor` that picks jobs from `queue.Queue` and runs the full review pipeline. |
| **Context Builder** | The pipeline component that assembles the LLM prompt from the diff and extracted symbol snippets, enforcing the 4000-token budget. |
| **SSE** | Server-Sent Events — a unidirectional HTTP streaming protocol used to push job state changes from Flask to the Next.js frontend in real time. |
| **Unified Diff** | The standard `diff -u` format showing changed lines prefixed with `+` (added) or `-` (removed) and context lines unprefixed. |
| **Terminal State** | A job status from which no further transitions occur: `COMPLETED`, `STATIC_FAILED`, or `SUPERSEDED`. |
| **Groq** | The LLM API provider hosting `llama-3.3-70b-versatile`, used for the AI code review step. |
| **Telemetry** | Per-job metrics tracked and displayed: `latency_ms`, `prompt_tokens`, `completion_tokens`, `cost_usd`, and `cache_hit`. |
