# ⚡ Quick Start - 5 Minutes to First PR Review

## Prerequisites
- Python 3.11+
- Groq API Key from https://console.groq.com

---

## Setup (2 minutes)

```bash
# 1. Go to backend
cd backend

# 2. Install dependencies
python -m venv venv
.\venv\Scripts\activate          # Windows
# source venv/bin/activate       # macOS/Linux
pip install -r requirements.txt

# 3. Configure API key
cp .env.example .env
# Edit .env and add: GROQ_API_KEY=gsk_your_actual_key_here

# 4. Verify setup
python check_setup.py
```

---

## Run (1 minute)

```bash
# Start the backend
python start.py
```

✅ Backend running at http://localhost:8000

---

## Test (2 minutes)

```bash
# In a new terminal (keep backend running)
cd backend
.\venv\Scripts\activate          # Activate venv again

# Test 1: Clean PR
python simulator.py single 1

# Test 2: Batch (20 PRs, test concurrency)
python simulator.py batch 20

# Test 3: Secret detection (should fail gate)
python simulator.py single 2 with_secret

# Test 4: Cache hit (zero LLM tokens)
python simulator.py cache
```

---

## View Results

```bash
# List all jobs
curl http://localhost:8000/jobs

# Get specific job
curl http://localhost:8000/jobs/1

# System status
curl http://localhost:8000/status
```

**Or visit**: http://localhost:8000/docs (interactive API docs)

---

## Expected Output

### Successful Submission
```json
{
  "job_id": 1,
  "status": "QUEUED",
  "message": "PR submitted successfully. Job ID: 1"
}
```

### Completed Job
```json
{
  "id": 1,
  "status": "COMPLETED",
  "review": {
    "summary": "Code looks good...",
    "findings": [...]
  },
  "prompt_tokens": 1234,
  "completion_tokens": 456,
  "cost_usd": 0.001234,
  "latency_ms": 2500,
  "cache_hit": false
}
```

### Gate Failure (Secret Detected)
```json
{
  "id": 2,
  "status": "STATIC_FAILED",
  "static_result": {
    "passed": false,
    "errors": ["Potential AWS Access Key detected..."]
  }
}
```

---

## Troubleshooting

**"GROQ_API_KEY not configured"**
→ Make sure `.env` file exists with real API key (not placeholder)

**"Module not found"**
→ Activate virtual environment: `.\venv\Scripts\activate`

**"Port 8000 in use"**
→ Change `API_PORT` in `.env` to 8001

---

## Key Commands

| Command | Purpose |
|---------|---------|
| `python start.py` | Start backend server |
| `python simulator.py single <n>` | Submit single PR |
| `python simulator.py batch <n>` | Submit batch of PRs |
| `python simulator.py cache` | Test caching |
| `python check_setup.py` | Verify environment |
| `pytest tests/ -v` | Run tests |

---

## What's Happening?

1. **Submit PR** → Creates job in SQLite
2. **Queue** → Async worker picks up job
3. **Gate Check** → Scans for secrets, validates syntax (0.3ms)
4. **Cache Check** → Looks for previous review of same commit (2ms)
5. **Context** → Extracts relevant code (4,000 token budget)
6. **AI Review** → Groq analyzes and returns findings (2-5s)
7. **Persist** → Saves results, caches for future, broadcasts update

---

## Demo Scenarios

```bash
# Scenario 1: Normal PR (should pass)
python simulator.py single 1 clean

# Scenario 2: AWS key in diff (should fail gate)
python simulator.py single 2 with_secret

# Scenario 3: Python syntax error (should fail gate)
python simulator.py single 3 syntax_error

# Scenario 4: Security improvement (should pass with findings)
python simulator.py single 4 auth_improvement

# Scenario 5: 20 PRs at once (test concurrency)
python simulator.py batch 20
```

---

## Next Steps

✅ **Backend is running** - Try the simulator  
✅ **API is working** - Check http://localhost:8000/docs  
✅ **Tests pass** - Run `pytest tests/ -v`  

**Now**: Connect frontend dashboard (Rohan) or integrate GitHub webhooks

---

**Full docs**: See `README.md` and `SETUP.md`
