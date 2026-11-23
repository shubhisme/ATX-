# High-Throughput Git PR Verification & Context Engine

**Group 2's Project** - A high-performance background system for Git Pull Request verification and AI-assisted code review.

## 🎯 Product Goal

We built a background pipeline that solves two critical problems with naive AI code review:

1. **Token Efficiency**: Sending entire repositories to LLMs creates unnecessary token usage, cost, and latency
2. **Concurrency**: Processing PRs synchronously creates bottlenecks when many developers submit PRs

## 🏗️ Architecture

```
GitHub/Simulator → FastAPI → Deterministic Gate → Commit Cache → Surgical Context → Groq Review → SQLite → WebSocket/Dashboard
```

### Core Components

- **Backend/API**: Python + FastAPI
- **Concurrency**: Native Python `asyncio.Queue` with 3 async worker tasks
- **Database**: SQLite with WAL mode via `aiosqlite`
- **AI Provider**: Groq SDK (llama-3.3-70b-versatile)
- **Frontend**: Next.js 14 dashboard
- **Live Updates**: FastAPI WebSockets

### Pipeline Stages

1. **PR Ingestion** - Receive PR, identify repo/commit/diff
2. **Deterministic Gate** - Scan for secrets, validate Python syntax (11 secret patterns)
3. **Commit Cache Check** - Reuse previous reviews for same commit SHA
4. **Surgical Context Gathering** - Extract only relevant code (4,000 token budget)
5. **Groq AI Review** - Structured review with findings
6. **Persistence** - Save results, telemetry, broadcast updates

## 📦 Project Structure

```
backend/
├── main.py              # FastAPI app, worker pool, orchestration (Shubh)
├── db.py                # SQLite async persistence layer
├── models.py            # Shared dataclasses and enums
├── config.py            # Environment configuration
├── simulator.py         # PR simulator for testing
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
│
├── gates/               # Deterministic checks (Chirag)
│   ├── __init__.py
│   └── detector.py      # Secret detection, syntax validation
│
├── context/             # Surgical context engine (Chirag)
│   ├── __init__.py
│   └── engine.py        # Import parsing, function extraction
│
├── agent/               # Groq review agent (Chirag)
│   ├── __init__.py
│   └── reviewer.py      # LLM review with structured output
│
├── sample_repo/         # Sample code for context testing
│   ├── auth.py
│   ├── payments.py
│   └── utils.py
│
└── tests/               # Test suite
    └── __init__.py

frontend/                # Next.js 14 dashboard (Rohan)
├── app/
│   ├── layout.tsx
│   └── page.tsx
├── package.json
└── ...
```

## 🚀 Setup & Installation

### Prerequisites

- Python 3.11+
- Node.js 18+
- Groq API key
- GitHub Personal Access Token (optional, for GitHub integration)

### Backend Setup

1. **Clone and navigate to backend**:
   ```bash
   cd backend
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env and add your keys:
   # GROQ_API_KEY=your_groq_api_key
   # GITHUB_TOKEN=your_github_token (optional)
   ```

5. **Run the backend**:
   ```bash
   python main.py
   ```
   
   Backend will start on `http://localhost:8000`

### Frontend Setup

1. **Navigate to frontend**:
   ```bash
   cd frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Run development server**:
   ```bash
   npm run dev
   ```
   
   Dashboard will start on `http://localhost:3000`

## 🧪 Testing the System

### Using the PR Simulator

The simulator provides several test scenarios:

#### 1. Submit a Single PR
```bash
python simulator.py single 1
```

Different scenarios:
```bash
python simulator.py single 2 with_secret      # Will fail gate (secret detected)
python simulator.py single 3 syntax_error     # Will fail gate (syntax error)
python simulator.py single 4 auth_improvement # Clean PR with improvements
python simulator.py single 5 clean           # Simple clean PR
```

#### 2. Submit Batch (Concurrency Test)
```bash
python simulator.py batch 20
```

Submits 20 PRs simultaneously to test concurrent processing.

#### 3. Test Commit Caching
```bash
python simulator.py cache
```

Submits two PRs with the same commit SHA. Second should be a cache hit (zero LLM tokens).

#### 4. Test Job Supersession
```bash
python simulator.py supersede
```

Submits two commits for the same PR number. First job should be marked as SUPERSEDED.

## 📊 API Endpoints

### Core Endpoints

- `POST /submit` - Submit a PR for review
  ```json
  {
    "pr_number": 1,
    "title": "Fix authentication bug",
    "commit_sha": "abc123...",
    "diff": "diff --git ...",
    "files": ["auth.py"]
  }
  ```

- `GET /jobs` - List all jobs (most recent first)
- `GET /jobs/{id}` - Get detailed job information
- `GET /status` - System status (queue size, workers, connections)
- `WS /ws` - WebSocket for live updates

### Example Response

```json
{
  "id": 1,
  "pr_number": 42,
  "title": "Add password hashing",
  "commit_sha": "abc123...",
  "status": "COMPLETED",
  "review": {
    "summary": "Good security improvement",
    "findings": [
      {
        "severity": "info",
        "file": "auth.py",
        "line": 18,
        "message": "Consider using bcrypt instead of PBKDF2",
        "suggestion": "import bcrypt"
      }
    ]
  },
  "prompt_tokens": 1234,
  "completion_tokens": 456,
  "cost_usd": 0.001234,
  "latency_ms": 2500,
  "cache_hit": false
}
```

## 🎭 Job Lifecycle

```
QUEUED → AI_REVIEWING → COMPLETED
              ↓
        STATIC_FAILED (gate rejected)
              ↓
        SUPERSEDED (newer commit arrived)
```

## 🔒 Security Features

### Secret Detection (11 Patterns)

- AWS Access Key / Secret Key
- GitHub Token
- Generic API Key
- Private Key (RSA/EC)
- Google API Key
- Slack Token
- Stripe Key
- Database Password
- JWT Token
- Twilio Auth

### Additional Checks

- Python syntax validation using AST
- Large diff warnings
- Binary file detection (future)

## 💰 Cost Tracking

Every job tracks:
- **Prompt tokens** - Input tokens sent to Groq
- **Completion tokens** - Output tokens from Groq
- **Estimated cost** - Based on current Groq pricing
  - Input: $0.59 per 1M tokens
  - Output: $0.79 per 1M tokens

Cache hits consume **zero new LLM tokens**.

## 📈 Performance Characteristics

- **Deterministic gate**: ~0.33ms (reported benchmark)
- **Cache lookup**: ~2ms (reported benchmark)
- **Full AI review**: ~2-5 seconds (depends on context size)
- **Concurrent workers**: 3 (configurable via `NUM_WORKERS`)
- **Context budget**: 4,000 tokens (configurable via `TOKEN_BUDGET`)

## 🎯 Success Metrics

A successful end-to-end demo shows:

1. ✅ Batch PR submission (20+ PRs) returns immediately
2. ✅ Workers process jobs concurrently
3. ✅ PRs with secrets/syntax errors fail at gate (no LLM call)
4. ✅ Duplicate commits reuse cached reviews (zero new tokens)
5. ✅ Valid PRs receive AI review with structured findings
6. ✅ Dashboard shows live status updates via WebSocket
7. ✅ Newer commits supersede older jobs
8. ✅ Telemetry tracked (tokens, cost, latency)

## 🤝 Team

- **Shubh**: Backend orchestration, FastAPI, worker pool, job lifecycle
- **Chirag**: Deterministic gates, surgical context engine, Groq agent
- **Rohan**: Next.js dashboard, WebSocket integration, UI/UX

## 📝 Configuration

Environment variables (`.env`):

```bash
# Required
GROQ_API_KEY=your_groq_api_key_here

# Optional
GITHUB_TOKEN=your_github_token
GITHUB_WEBHOOK_SECRET=webhook_secret

# System
DB_PATH=pr_engine.db
NUM_WORKERS=3
API_PORT=8000
```

## 🔮 Future Enhancements

- GitHub webhook integration
- Support for more languages (JavaScript, Go, etc.)
- More sophisticated context ranking
- Incremental review (only changed functions)
- Review quality feedback loop
- Distributed workers with Redis (scaling path)

## 📚 Documentation

See `coding-agent-project-context.md` for complete architectural decisions, ownership boundaries, and design principles.

## ⚠️ Important Notes

- This is a **background processing system**, not a synchronous review tool
- PRs are queued and processed asynchronously
- Results are delivered via WebSocket and REST API
- SQLite with WAL mode supports concurrent reads/writes
- Do NOT send entire repositories to the LLM (defeats the purpose)
- Cache invalidation is based on commit SHA (not PR content)

---

Built for high-throughput PR review with minimal LLM costs and maximum developer velocity.
