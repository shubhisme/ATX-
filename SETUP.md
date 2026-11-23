# Setup Guide - PR Verification Engine

This guide walks you through setting up the complete system from scratch.

## Prerequisites

✅ **Python 3.11+** installed  
✅ **Node.js 18+** installed  
✅ **Groq API Key** (get from https://console.groq.com)  
✅ **GitHub Personal Access Token** (optional, for GitHub integration)

---

## Step 1: Backend Setup

### 1.1 Navigate to Backend Directory

```bash
cd backend
```

### 1.2 Create Python Virtual Environment

**On Windows:**
```powershell
python -m venv venv
.\venv\Scripts\activate
```

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt.

### 1.3 Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- FastAPI (web framework)
- uvicorn (ASGI server)
- aiosqlite (async SQLite)
- groq (AI provider)
- websockets (live updates)
- pytest (testing)

### 1.4 Configure Environment Variables

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your credentials:
   ```bash
   # Required - Get from https://console.groq.com
   GROQ_API_KEY=gsk_your_actual_groq_api_key_here

   # Optional - For GitHub integration
   GITHUB_TOKEN=ghp_your_github_token_here
   GITHUB_WEBHOOK_SECRET=optional_secret

   # System configuration (defaults are fine)
   DB_PATH=pr_engine.db
   NUM_WORKERS=3
   API_PORT=8000
   ```

   ⚠️ **IMPORTANT**: Replace `gsk_your_actual_groq_api_key_here` with your real Groq API key!

### 1.5 Verify Installation

```bash
python -c "import fastapi, aiosqlite, groq; print('✅ All dependencies installed')"
```

---

## Step 2: Frontend Setup (Next.js Dashboard)

### 2.1 Navigate to Frontend Directory

```bash
cd ../frontend
```

### 2.2 Install Node Dependencies

```bash
npm install
```

This installs Next.js 14, React, Tailwind CSS, and other frontend dependencies.

### 2.3 Configure Backend URL (if needed)

The frontend expects the backend at `http://localhost:8000`. If your backend runs on a different port, update the API calls in the frontend code.

---

## Step 3: Running the System

### 3.1 Start the Backend (Terminal 1)

```bash
cd backend
python start.py
```

You should see:
```
🚀 Starting PR Verification Engine...
📡 API will be available at: http://localhost:8000
📊 API docs at: http://localhost:8000/docs
🔌 WebSocket at: ws://localhost:8000/ws
```

The backend will:
- Initialize the SQLite database
- Start 3 async worker threads
- Begin listening for PR submissions

### 3.2 Start the Frontend (Terminal 2)

```bash
cd frontend
npm run dev
```

You should see:
```
▲ Next.js 14.x.x
- Local:        http://localhost:3000
```

Open your browser to `http://localhost:3000` to see the dashboard.

---

## Step 4: Test the System

### 4.1 Quick Health Check

Visit http://localhost:8000 in your browser. You should see:
```json
{
  "service": "PR Verification Engine",
  "status": "running",
  "workers": 3
}
```

### 4.2 API Documentation

Visit http://localhost:8000/docs for interactive API documentation (Swagger UI).

### 4.3 Submit a Test PR

**Option A: Using the Simulator (Recommended)**

```bash
cd backend
python simulator.py single 1
```

**Option B: Using curl**

```bash
curl -X POST http://localhost:8000/submit \
  -H "Content-Type: application/json" \
  -d '{
    "pr_number": 1,
    "title": "Test PR",
    "commit_sha": "0000000000000000000000000000000000000001",
    "diff": "diff --git a/test.py b/test.py\n+def hello():\n+    return \"world\"",
    "files": ["test.py"]
  }'
```

**Expected Response:**
```json
{
  "job_id": 1,
  "status": "QUEUED",
  "message": "PR submitted successfully. Job ID: 1"
}
```

### 4.4 Check Job Status

```bash
curl http://localhost:8000/jobs/1
```

---

## Step 5: Advanced Testing Scenarios

### Test 1: Batch Submission (Concurrency)

Submit 20 PRs simultaneously to test the async worker pool:

```bash
python simulator.py batch 20
```

Watch the backend logs to see workers processing jobs concurrently.

### Test 2: Secret Detection (Gate Failure)

```bash
python simulator.py single 2 with_secret
```

This PR contains an AWS key and should fail the deterministic gate without calling the LLM.

### Test 3: Syntax Error (Gate Failure)

```bash
python simulator.py single 3 syntax_error
```

This PR has Python syntax errors and should fail the gate.

### Test 4: Commit Caching

```bash
python simulator.py cache
```

Submits two PRs with the same commit SHA. The second should be served from cache (zero LLM tokens).

### Test 5: Job Supersession

```bash
python simulator.py supersede
```

Submits two commits for the same PR. The older job should be marked as SUPERSEDED.

---

## Step 6: Run Tests

### Backend Tests

```bash
cd backend
pytest tests/ -v
```

Expected output:
```
tests/test_gates.py::test_clean_code_passes_gate PASSED
tests/test_gates.py::test_aws_key_detected PASSED
tests/test_gates.py::test_github_token_detected PASSED
...
```

---

## Verification Checklist

After setup, verify these work:

- [ ] Backend starts without errors
- [ ] Frontend loads at http://localhost:3000
- [ ] API docs accessible at http://localhost:8000/docs
- [ ] Can submit a PR via simulator
- [ ] Job appears in dashboard
- [ ] Job status updates in real-time (WebSocket)
- [ ] Completed jobs show review findings
- [ ] PRs with secrets fail at gate
- [ ] Cache hits work (duplicate commits)
- [ ] Batch submission processes concurrently

---

## Common Issues & Troubleshooting

### Issue: "GROQ_API_KEY not configured"

**Solution**: Make sure you created `.env` file and added your actual Groq API key (not the example placeholder).

### Issue: "Module not found" errors

**Solution**: Make sure you activated the virtual environment:
```bash
# Windows
.\venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### Issue: Port 8000 already in use

**Solution**: Change `API_PORT` in `.env` to a different port (e.g., 8001).

### Issue: SQLite database locked

**Solution**: Stop all backend processes and delete `pr_engine.db*` files, then restart.

### Issue: Frontend can't connect to backend

**Solution**: 
1. Verify backend is running (`curl http://localhost:8000`)
2. Check CORS settings in `main.py` include your frontend URL
3. Update frontend API URLs if backend port changed

### Issue: Tests fail

**Solution**: Make sure you're in the backend directory and virtual environment is activated:
```bash
cd backend
source venv/bin/activate  # or .\venv\Scripts\activate on Windows
pytest tests/ -v
```

---

## Next Steps

Once everything is running:

1. **Explore the Dashboard**: Watch jobs flow through the pipeline in real-time
2. **Review the API Docs**: http://localhost:8000/docs
3. **Check the Logs**: Backend terminal shows detailed processing info
4. **Experiment**: Try different PR scenarios with the simulator
5. **Read the Code**: Start with `backend/main.py` to understand the orchestration

---

## Project Structure Reference

```
backend/
├── main.py              # FastAPI app + worker pool
├── db.py                # SQLite async operations
├── models.py            # Data structures
├── config.py            # Configuration
├── simulator.py         # PR testing tool
├── start.py             # Launch script
├── gates/               # Secret detection, syntax checks
├── context/             # Surgical context gathering
├── agent/               # Groq AI review
├── sample_repo/         # Sample code for testing
└── tests/               # Test suite

frontend/
└── app/                 # Next.js dashboard
```

---

## Additional Resources

- **Groq Documentation**: https://console.groq.com/docs
- **FastAPI Documentation**: https://fastapi.tiangolo.com
- **Next.js Documentation**: https://nextjs.org/docs
- **Project Architecture**: See `coding-agent-project-context.md`

---

## Support

If you encounter issues:

1. Check the backend logs (terminal 1)
2. Check browser console (F12) for frontend errors
3. Verify `.env` configuration
4. Ensure all dependencies are installed
5. Review this setup guide step-by-step

**Team Members:**
- **Shubh**: Backend orchestration
- **Chirag**: Gates, context, agent
- **Rohan**: Frontend dashboard
