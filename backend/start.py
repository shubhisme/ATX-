"""
Quick start script for the PR Verification Engine.
Runs the FastAPI server with uvicorn.
"""
import uvicorn
from config import API_PORT

if __name__ == "__main__":
    print("🚀 Starting PR Verification Engine...")
    print(f"📡 API will be available at: http://localhost:{API_PORT}")
    print(f"📊 API docs at: http://localhost:{API_PORT}/docs")
    print(f"🔌 WebSocket at: ws://localhost:{API_PORT}/ws")
    print("\nPress Ctrl+C to stop\n")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=API_PORT,
        reload=True,
        log_level="info"
    )
