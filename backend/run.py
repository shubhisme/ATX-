"""
Safe server startup with error handling.
"""
import sys
import os


def check_env():
    """Check if .env exists."""
    if not os.path.exists('.env'):
        print("⚠️  Warning: .env file not found")
        print("Creating .env from template...")
        
        if os.path.exists('.env.example'):
            with open('.env.example', 'r') as f:
                template = f.read()
            
            with open('.env', 'w') as f:
                f.write(template)
            
            print("✅ Created .env file")
            print("\n⚠️  IMPORTANT: Edit .env and add your GROQ_API_KEY")
            print("   The server will start but API calls will fail without it.\n")
        else:
            print("❌ .env.example not found")
            return False
    
    # Check if API key is set
    from dotenv import load_dotenv
    load_dotenv()
    
    groq_key = os.getenv('GROQ_API_KEY', '')
    if not groq_key or groq_key.startswith('your_'):
        print("⚠️  Warning: GROQ_API_KEY not configured in .env")
        print("   The server will start but AI reviews will fail.\n")
    
    return True


def main():
    """Start the server."""
    
    print("🔍 Pre-flight checks...")
    
    # Check environment
    if not check_env():
        print("\n❌ Setup incomplete")
        return 1
    
    print("✅ Environment OK\n")
    
    # Import and run
    try:
        import uvicorn
        from config import API_PORT
        
        print("🚀 Starting PR Verification Engine...")
        print(f"📡 API: http://localhost:{API_PORT}")
        print(f"📊 Docs: http://localhost:{API_PORT}/docs")
        print(f"🔌 WebSocket: ws://localhost:{API_PORT}/ws")
        print("\nPress Ctrl+C to stop\n")
        
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=API_PORT,
            reload=False,  # Disable reload to avoid issues
            log_level="info"
        )
        
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped")
        return 0
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
