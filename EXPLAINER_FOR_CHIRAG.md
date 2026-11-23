# 💡 The Plain-English Guide to Our PR Verification Engine
### *Everything you need to know to speak with 100% confidence to senior engineers*

---

## 1. The 30-Second Elevator Pitch

> *"Most companies that use AI to review Pull Requests make two big mistakes: they dump the entire codebase into ChatGPT (which costs a fortune and is slow), and they process PRs one-by-one synchronously (which creates huge bottlenecks).*
>
> *Our project is a **High-Throughput PR Verification Engine**. We put zero-cost security and syntax checks in front of the AI, only feed the AI the exact code slices it needs to see, and run everything in an asynchronous background queue with smart caching and a live dashboard."*

---

## 2. The Real-World Problem We Are Solving

Imagine a software team with 50 engineers opening 100 Pull Requests (PRs) a day.

### The Naive Way (What bad tools do):
1. An engineer opens a PR that changes 3 lines of code in `auth.py`.
2. The naive tool reads **all 200 files in the repository** and sends all of them to an LLM (like GPT-4).
3. **The Problems:**
   - **Cost Explosion:** 100,000 tokens per review × 100 PRs/day = Hundreds of dollars wasted daily on AI fees.
   - **Slow Latency:** Sending huge context takes 30 to 60 seconds per review.
   - **Stupid Waste:** If the PR has a syntax error or leaks a secret AWS password, why are we paying an AI \$0.50 to tell us that? A simple regex check could tell us in 1 millisecond for \$0.00!
   - **Traffic Jams:** If 10 developers push commits at 2:00 PM, a synchronous script freezes and reviews them one-by-one. People wait 20 minutes for feedback.

### Our Solution:
1. **Filter first for free:** Run instant checks (regex secret scanner, python syntax check). If it fails, fail immediately in **0.3 ms** at **\$0.00 cost**.
2. **Surgical Context:** Don't send the whole repo. If you changed `app.py`, we only inspect what `app.py` directly imports (`auth.py`, `database.py`).
3. **Async Queue:** PRs enter a background queue. 3 workers review PRs simultaneously.
4. **Cache:** If someone pushes the same commit twice, don't call the AI again. Return the saved review instantly.

---

## 3. Step-by-Step: The Journey of a Pull Request

Let's walk through an actual example: **Alice submits a PR changing 5 lines in `app.py`**.

```
[ Alice submits PR ]
        │
        ▼
1. FAST DETERMINISTIC GATE (< 1 millisecond, $0.00 spent)
   - Did Alice accidentally hardcode an AWS key or password? (Regex scan)
   - Did Alice make a Python syntax error (like a missing colon)? (ast.parse)
   │
   ├─► IF YES (Secret or Syntax error):
   │     STOP IMMEDIATELY!
   │     Mark status as STATIC_FAILED.
   │     Save result in SQLite.
   │     Zero tokens consumed. Zero dollars spent.
   │
   └─► IF NO (Everything clean):
         Move to Step 2.
        │
        ▼
2. COMMIT-SHA CACHE CHECK
   - Have we already reviewed this exact git commit SHA?
   │
   ├─► IF YES:
   │     Return the cached review instantly from SQLite!
   │     Status = COMPLETED (cached). Zero LLM tokens.
   │
   └─► IF NO:
         Push into Async Queue (asyncio.Queue).
        │
        ▼
3. SURGICAL CONTEXT EXTRACTION (The Smart Part!)
   - Alice modified `app.py`.
   - Instead of reading 100 repo files, our `dependency_resolver` parses the imports:
       "Oh, `app.py` imports `verify_token` from `auth.py` and `fetch_user` from `database.py`."
   - Our `symbol_reader` pulls ONLY those specific functions from `auth.py` and `database.py`.
   - We package the Diff + only those functions into a neat prompt (bounded to 4,000 tokens max).
        │
        ▼
4. AI REVIEW AGENT (Groq LPU)
   - Sends the surgical package to Groq's fast LLM (`compound-beta`).
   - Receives back structured JSON with findings:
       - Severity: `warning`
       - Category: `security`
       - Line: 52
       - Message: "Token expiration is checked after database lookup instead of before."
   - Tracks tokens used and calculates estimated cost in USD.
        │
        ▼
5. PERSISTENCE & DASHBOARD
   - Everything is saved to SQLite (`db.py`).
   - Rohan's Next.js dashboard updates in real-time showing Alice's PR, its review findings, latency (e.g., 420ms), and cost ($0.00).
```

---

## 4. What YOU (Chirag) Built — Plain and Simple

You own the **Intelligence Layer** and the **Database Layer**. Here are the 4 pieces you built:

### Piece 1: The Deterministic Gates (`backend/gates/`)
* **What it does:** The bouncer at the door.
* **Files:** `secret_scanner.py`, `syntax_checker.py`, `gate_runner.py`
* **How it works:**
  - `secret_scanner.py` runs regular expressions to catch AWS keys (`AKIA...`), GitHub tokens (`ghp_...`), JWTs, and OpenAI keys (`sk-...`). When it finds one, it redacts it (`AKIA****`) and blocks the PR.
  - `syntax_checker.py` uses Python's built-in `ast.parse()` to see if the modified Python code can even compile.
  - `gate_runner.py` runs both in parallel.
* **Why it matters:** The PRD required this to take under 100 milliseconds. Ours takes **0.33 milliseconds** (300 times faster than requirement!).

### Piece 2: The Context Engine (`backend/context/`)
* **What it does:** The surgical scalpel.
* **Files:** `dependency_resolver.py`, `symbol_reader.py`
* **How it works:**
  - `dependency_resolver.py` looks at the files in the PR diff and inspects their `import` statements using Python's Abstract Syntax Tree (`ast`). It says: *"This file depends on `auth.py`, but it doesn't care about `payment.py` or `email.py`."*
  - `symbol_reader.py` opens `auth.py`, finds the exact function being called (e.g., `def verify_token`), extracts just that function's code, and respects a strict token budget (4,000 tokens).
* **Why it matters:** This cuts LLM token usage by **80% to 90%** compared to sending whole files or whole repos.

### Piece 3: The LLM Review Agent (`backend/agent/`)
* **What it does:** The code reviewer.
* **Files:** `review_agent.py`, `token_tracker.py`, `prompts.py`
* **How it works:**
  - Formats a clean prompt: *"You are a senior reviewer. Here is the diff and here are the imported dependencies. Give me a JSON response with severity, line number, category, and fix suggestion."*
  - Calls Groq's high-speed API (`AsyncGroq`).
  - `token_tracker.py` calculates the wall-clock milliseconds, input tokens, output tokens, and dollar cost.

### Piece 4: The Database Layer (`backend/db.py`)
* **What it does:** The brain and memory.
* **File:** `backend/db.py`
* **How it works:**
  - Uses `aiosqlite` with Write-Ahead Logging (`WAL` mode) so multiple workers can read/write without locking each other up.
  - Has 4 tables: `jobs` (tracks status like `QUEUED`, `AI_REVIEWING`), `review_cache` (saves reviews by commit SHA), `review_findings` (stores bugs/warnings), and `static_gate_results` (records gate pass/fail).
  - Handles **supersession**: if Alice pushes Commit #1 and then pushes Commit #2 immediately, our DB automatically marks Commit #1 as `SUPERSEDED` so we don't waste time reviewing outdated code!

---

## 5. Who Does What in the Team

| Team Member | Domain | Components |
|---|---|---|
| **Chirag (You)** | **Intelligence + Database** | Deterministic Gates (`gates/`), Context Engine (`context/`), Groq Agent (`agent/`), SQLite DB (`db.py`), Sample Repo (`sample_repo/`) |
| **Shubh** | **Backend Core + Queue** | FastAPI Server (`main.py`), Async Worker Pool (`queue_manager.py`), GitHub Webhook (`webhook.py`), ngrok tunnel |
| **Rohan** | **Frontend Dashboard** | Next.js 14 App (`frontend/`), Queue Monitor UI, Diff Viewer with inline comments, Telemetry Charts, Batch PR Simulator |

---

## 6. Senior Engineer Q&A Cheat Sheet (Memorize These!)

If a senior engineer walks up to your screen and asks questions, here is how you answer:

### Q1: *"What is your queue architecture and tech stack?"*
> **Answer:**
> *"We use FastAPI for the backend API and Python's native `asyncio.Queue` for the worker pool. We have a configurable pool of async worker tasks (default 3) running concurrently in the same process.
> For persistence and deduplication caching, we use SQLite in WAL mode via `aiosqlite`.
> For the AI layer, we use Groq's SDK targeting their LPU inference engine with `compound-beta` to get sub-second review generation.
> The frontend is Next.js 14 with Tailwind and shadcn."*

### Q2: *"Why did you use `asyncio.Queue` instead of Celery or Redis?"*
> **Answer:**
> *"For this 5-hour build window and single-instance architecture, `asyncio.Queue` provides zero-configuration, sub-millisecond in-memory dispatch, and native Python async/await without needing external infrastructure.
> However, our architecture is decoupled: the worker coroutine interface accepts job contexts in the exact same pattern required by Redis Streams or Celery, which is our documented scale path for distributed nodes."*

### Q3: *"How does your surgical context gathering actually work?"*
> **Answer:**
> *"Instead of naive repo dumping or embeddings/RAG, we use deterministic AST parsing.
> When a diff arrives, `dependency_resolver` parses the `import` and `from ... import` statements in the modified files.
> We resolve those imports to local files in the repository.
> Then `symbol_reader` extracts only the top-level function and class signatures that are referenced, truncating at a 4,000 token budget. This reduces prompt tokens by up to 90% while giving the LLM the exact context of the functions being called."*

### Q4: *"How fast are your deterministic gates and what do they catch?"*
> **Answer:**
> *"They run in under 1 millisecond — specifically benchmarked at 0.33 ms, well under the 100 ms PRD threshold.
> They catch 11 types of secrets — AWS keys, JWTs, GitHub PATs, OpenAI keys, Slack tokens, private keys — and automatically redact them with asterisks so secrets never enter logs.
> They also check Python AST syntax on modified files. If either fails, the job immediately terminates with `STATIC_FAILED` and \$0.00 LLM spend."*

### Q5: *"What happens if a developer pushes 3 commits in rapid succession to the same PR?"*
> **Answer:**
> *"We have PR supersession built into `db.py` and the queue. When a new commit arrives for PR #X, `supersede_pr_jobs(pr_number)` updates all previous active or queued jobs for that PR to `SUPERSEDED` status. The workers drop or ignore the superseded jobs, preventing wasted tokens and stale review comments."*

### Q6: *"How do you handle commit deduplication?"*
> **Answer:**
> *"Before pushing a job to the LLM worker, we check our `review_cache` table using the `commit_sha` as the primary key. If that commit SHA was already reviewed, we return the cached JSON review in under 2 milliseconds with 0 tokens consumed."*

---

## 7. Quick Summary of What You Can Show on Screen

If someone asks: *"Show me what you've done"*:
1. Open [`backend/tests/test_chirag_components.py`](file:///d:/Github%20Store/ATX%20Placement/ATX-/backend/tests/test_chirag_components.py) and run it:
   ```powershell
   python -m unittest discover -s backend/tests
   ```
2. Show them the terminal: **13 tests passing in 0.20 seconds**.
3. Point out:
   - Secret scan caught AWS key, JWT, GitHub token and redacted them.
   - Syntax checker caught broken code.
   - Dependency resolver mapped `app.py` → `auth.py`, `database.py`, `utils.py`.
   - SQLite database wrote and retrieved cached jobs, findings, and supersessions.
   - Everything is already pushed to GitHub (`main` branch)!
