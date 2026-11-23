@echo off
echo ======================================================================
echo 🚀 STARTING PR VERIFICATION ENGINE (Full Stack)
echo ======================================================================

echo [1/2] Starting FastAPI Backend on http://localhost:8000...
start "Backend - FastAPI" cmd /k "cd /d %~dp0backend && python start.py"

echo [2/2] Starting Next.js Frontend Dashboard on http://localhost:3000...
start "Frontend - Next.js" cmd /k "cd /d %~dp0frontend && npm run dev"

echo ======================================================================
echo ✅ Both services launched!
echo Dashboard: http://localhost:3000
echo API Docs:  http://localhost:8000/docs
echo ======================================================================
pause
