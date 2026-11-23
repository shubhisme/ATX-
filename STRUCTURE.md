# Project Structure Overview

## 📁 Complete Directory Tree

```
ATX selection/
│
├── 📄 README.md                          ← Main documentation
├── 📄 SETUP.md                           ← Detailed setup guide
├── 📄 QUICKSTART.md                      ← 5-minute quick start
├── 📄 PROJECT_SUMMARY.md                 ← Build summary
├── 📄 STRUCTURE.md                       ← This file
├── 📄 coding-agent-project-context.md    ← Architecture specification
├── 📄 .gitignore                         ← Git ignore rules
│
├── 📂 backend/                           ← Python FastAPI Backend
│   │
│   ├── 🐍 main.py                        ← FastAPI app + async workers
│   ├── 🐍 db.py                          ← SQLite async operations
│   ├── 🐍 models.py                      ← Data structures (PRJobRow, etc.)
│   ├── 🐍 config.py                      ← Environment configuration
│   ├── 🐍 start.py                       ← Server launch script
│   ├── 🐍 check_setup.py                 ← Pre-flight environment check
│   ├── 🐍 simulator.py                   ← PR testing tool
│   │
│   ├── 📄 requirements.txt               ← Python dependencies
│   ├── 📄 .env.example                   ← Environment template
│   │
│   ├── 📂 gates/                         ← Deterministic checks (Chirag)
│   │   ├── 🐍 __init__.py
│   │   └── 🐍 detector.py                ← Secret detection + syntax validation
│   │
│   ├── 📂 context/                       ← Surgical context engine (Chirag)
│   │   ├── 🐍 __init__.py
│   │   └── 🐍 engine.py                  ← Import parsing, function extraction
│   │
│   ├── 📂 agent/                         ← Groq AI review (Chirag)
│   │   ├── 🐍 __init__.py
│   │   └── 🐍 reviewer.py                ← LLM review with Groq SDK
│   │
│   ├── 📂 sample_repo/                   ← Sample code for testing
│   │   ├── 🐍 __init__.py
│   │   ├── 🐍 auth.py                    ← Authentication module
│   │   ├── 🐍 payments.py                ← Payment processing
│   │   └── 🐍 utils.py                   ← Utility functions
│   │
│   └── 📂 tests/                         ← Test suite
│       ├── 🐍 __init__.py
│       ├── 🐍 test_gates.py              ← Gate tests (secrets, syntax)
│       └── 🐍 test_context.py            ← Context gathering tests
│
└── 📂 frontend/                          ← Next.js 14 Dashboard (Rohan)
    ├── 📂 app/
    │   ├── 📂 fonts/
    │   ├── ⚛️ layout.tsx                 ← Root layout
    │   ├── ⚛️ page.tsx                   ← Main page
    │   ├── 🎨 globals.css                ← Global styles
    │   └── 📄 favicon.ico
    │
    ├── 📂 node_modules/                  ← NPM dependencies (installed)
    ├── 📄 package.json                   ← NPM config
    ├── 📄 package-lock.json
    ├── 📄 next.config.mjs                ← Next.js config
    ├── 📄 tailwind.config.ts             ← Tailwind CSS config
    ├── 📄 tsconfig.json                  ← TypeScript config
    ├── 📄 postcss.config.mjs
    └── 📄 .gitignore
```

---

## 🎯 Component Responsibilities

### Core Backend Files

| File | Purpose | Owner |
|------|---------|-------|
| `main.py` | FastAPI app, worker pool, job orchestration | Shubh |
| `db.py` | SQLite async CRUD, caching, supersession | Shubh |
| `models.py` | Shared dataclasses, enums, type definitions | Shared |
| `config.py` | Environment variables, settings | Shared |

### Pipeline Modules

| Module | Purpose | Owner | Key Functions |
|--------|---------|-------|---------------|
| `gates/` | Deterministic checks | Chirag | `run_gate()` |
| `context/` | Surgical context | Chirag | `gather_context()` |
| `agent/` | AI review | Chirag | `review_pr()` |

### Utilities & Testing

| File | Purpose |
|------|---------|
| `simulator.py` | PR submission testing (single, batch, cache, supersede) |
| `start.py` | Quick server launch |
| `check_setup.py` | Pre-flight environment verification |
| `tests/test_gates.py` | Gate functionality tests |
| `tests/test_context.py` | Context gathering tests |

### Documentation

| File | Purpose | Audience |
|------|---------|----------|
| `README.md` | Complete project documentation | All |
| `SETUP.md` | Step-by-step setup guide | Setup |
| `QUICKSTART.md` | 5-minute quick start | Developers |
| `PROJECT_SUMMARY.md` | Build summary and deliverables | Team/Review |
| `STRUCTURE.md` | This file - directory overview | Navigation |
| `coding-agent-project-context.md` | Architecture spec | Architects |

---

## 📊 Statistics

- **Total Files**: 174 (Python, Markdown, config)
- **Python Modules**: 15 core files
- **Test Files**: 2 (gates, context)
- **Documentation**: 6 markdown files
- **Sample Repo Files**: 3 Python files
- **Frontend**: Next.js 14 with TypeScript

---

## 🔄 Data Flow

```
1. PR Submission
   ↓
2. main.py (POST /submit)
   - Creates job in db.py
   - Adds to asyncio.Queue
   ↓
3. Worker picks up job
   ↓
4. gates/detector.py
   - Secret detection
   - Syntax validation
   ↓ (if passed)
5. db.py (cache check)
   ↓ (if cache miss)
6. context/engine.py
   - Parse imports (AST)
   - Extract functions
   - Respect token budget
   ↓
7. agent/reviewer.py
   - Call Groq API
   - Get structured findings
   ↓
8. db.py
   - Save results
   - Cache for future
   ↓
9. WebSocket broadcast
   - Notify frontend
```

---

## 🗄️ Database Schema

**jobs** table:
- id, pr_number, title, commit_sha
- diff, status, files
- static_result, review
- prompt_tokens, completion_tokens, cost_usd
- queued_at, started_at, completed_at
- latency_ms, cache_hit

**commit_cache** table:
- commit_sha (PK)
- review, prompt_tokens, completion_tokens, cost_usd
- created_at

---

## 🌐 API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/submit` | Submit PR for review |
| GET | `/jobs` | List all jobs |
| GET | `/jobs/{id}` | Get job details |
| GET | `/status` | System status |
| WS | `/ws` | WebSocket updates |
| GET | `/` | Health check |
| GET | `/docs` | Swagger API docs |

---

## 🧪 Test Commands

```bash
# Backend setup verification
python check_setup.py

# Run test suite
pytest tests/ -v

# Single PR test
python simulator.py single 1

# Batch test (20 PRs)
python simulator.py batch 20

# Cache test
python simulator.py cache

# Supersession test
python simulator.py supersede
```

---

## 📦 Dependencies

**Backend** (requirements.txt):
- fastapi==0.115.6
- uvicorn[standard]==0.34.0
- websockets==14.1
- aiosqlite==0.20.0
- groq==0.13.0
- python-dotenv==1.0.1
- pytest==8.3.4
- pytest-asyncio==0.24.0
- httpx==0.28.1

**Frontend** (package.json):
- next@14.x
- react@18.x
- tailwindcss@3.x
- typescript@5.x

---

## 🔐 Configuration Files

**.env** (create from .env.example):
```bash
GROQ_API_KEY=your_key_here
GITHUB_TOKEN=optional
DB_PATH=pr_engine.db
NUM_WORKERS=3
API_PORT=8000
```

**config.py** (hardcoded):
- MAX_DIFF_SIZE=100,000
- MAX_BATCH_SIZE=20
- TOKEN_BUDGET=4,000

---

## 🎭 Job Status Flow

```
QUEUED
  ↓
  ├─→ STATIC_FAILED (gate rejected)
  │
  ↓ (gate passed)
AI_REVIEWING
  ↓
  ├─→ COMPLETED (success or cache hit)
  └─→ SUPERSEDED (newer commit arrived)
```

---

## 🚀 Deployment Checklist

- [ ] Backend dependencies installed
- [ ] `.env` configured with Groq API key
- [ ] Database initialized (automatic on first run)
- [ ] Port 8000 available (or changed in `.env`)
- [ ] Frontend dependencies installed (`npm install`)
- [ ] Tests passing (`pytest tests/ -v`)
- [ ] Sample PRs working (`python simulator.py batch 5`)

---

## 📞 Quick Reference

**Start Backend**: `python start.py`  
**Start Frontend**: `npm run dev` (in frontend/)  
**Test PR**: `python simulator.py single 1`  
**Check Status**: `curl http://localhost:8000/status`  
**API Docs**: http://localhost:8000/docs  

---

**Last Updated**: Initial build  
**Total Lines of Code**: ~2,500+ (excluding node_modules)  
**Architecture**: FastAPI + asyncio + SQLite + Groq + Next.js
