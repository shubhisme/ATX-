"""
Pre-flight check script to verify environment setup.
Run this before starting the server to catch configuration issues early.
"""
import sys
import os
from pathlib import Path


def check_python_version():
    """Verify Python version is 3.11+"""
    version = sys.version_info
    if version.major == 3 and version.minor >= 11:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor} - Need 3.11+")
        return False


def check_dependencies():
    """Check if required packages are installed."""
    required = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("aiosqlite", "aiosqlite"),
        ("groq", "Groq SDK"),
        ("websockets", "WebSockets"),
        ("pytest", "Pytest"),
    ]
    
    all_ok = True
    for module, name in required:
        try:
            __import__(module)
            print(f"✅ {name}")
        except ImportError:
            print(f"❌ {name} - Run: pip install {module}")
            all_ok = False
    
    return all_ok


def check_env_file():
    """Check if .env file exists and has required keys."""
    env_path = Path(".env")
    
    if not env_path.exists():
        print("❌ .env file not found")
        print("   Run: cp .env.example .env")
        return False
    
    print("✅ .env file exists")
    
    # Check for Groq API key
    with open(env_path) as f:
        content = f.read()
    
    if "GROQ_API_KEY=" in content:
        # Check if it's not the placeholder
        for line in content.split('\n'):
            if line.startswith('GROQ_API_KEY='):
                key = line.split('=', 1)[1].strip()
                if key and not key.startswith('your_') and len(key) > 20:
                    print("✅ GROQ_API_KEY configured")
                    return True
                else:
                    print("⚠️  GROQ_API_KEY looks like placeholder")
                    print("   Get your key from: https://console.groq.com")
                    return False
    
    print("❌ GROQ_API_KEY not found in .env")
    return False


def check_sample_repo():
    """Verify sample_repo exists for context gathering."""
    sample_path = Path("sample_repo")
    
    if not sample_path.exists():
        print("❌ sample_repo directory not found")
        return False
    
    py_files = list(sample_path.glob("*.py"))
    if len(py_files) >= 2:
        print(f"✅ sample_repo ({len(py_files)} Python files)")
        return True
    else:
        print("⚠️  sample_repo has few Python files")
        return True


def check_port_available(port=8000):
    """Check if the API port is available."""
    import socket
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('127.0.0.1', port))
        sock.close()
        print(f"✅ Port {port} available")
        return True
    except OSError:
        print(f"⚠️  Port {port} already in use")
        print(f"   Change API_PORT in .env or stop other process")
        return False


def main():
    """Run all pre-flight checks."""
    print("🔍 Running Pre-Flight Checks...\n")
    
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Environment File", check_env_file),
        ("Sample Repository", check_sample_repo),
        ("API Port", check_port_available),
    ]
    
    results = []
    
    for name, check_func in checks:
        print(f"\n{name}:")
        result = check_func()
        results.append((name, result))
    
    # Summary
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    
    all_passed = all(result for _, result in results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print("="*50)
    
    if all_passed:
        print("\n🎉 All checks passed! You can start the server:")
        print("   python start.py")
    else:
        print("\n⚠️  Some checks failed. Fix the issues above before starting.")
        sys.exit(1)


if __name__ == "__main__":
    main()
