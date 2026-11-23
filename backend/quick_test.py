"""
Quick test to verify all imports work before starting server.
"""
print("Testing imports...")

try:
    import asyncio
    print("✅ asyncio")
    
    import fastapi
    print("✅ fastapi")
    
    import uvicorn
    print("✅ uvicorn")
    
    import aiosqlite
    print("✅ aiosqlite")
    
    import groq
    print("✅ groq")
    
    import websockets
    print("✅ websockets")
    
    # Test project imports
    import db
    print("✅ db")
    
    import models
    print("✅ models")
    
    import config
    print("✅ config")
    
    from gates import run_gate
    print("✅ gates")
    
    from context import gather_context
    print("✅ context")
    
    from agent import review_pr
    print("✅ agent")
    
    print("\n" + "="*50)
    print("✅ ALL IMPORTS SUCCESSFUL!")
    print("="*50)
    print("\nYou can now start the server:")
    print("  python start.py")
    
except ImportError as e:
    print(f"\n❌ Import failed: {e}")
    print("\nRun: pip install -r requirements.txt")
