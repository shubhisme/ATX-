"""
Real-time queue and worker monitor.
Run this alongside the backend to watch workers process jobs in real-time.
"""
import asyncio
import httpx
import sys
from datetime import datetime


API_BASE = "http://localhost:8000"


async def get_status():
    """Get system status."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/status", timeout=5.0)
        return response.json()


async def monitor_loop():
    """Continuously monitor and display worker status."""
    
    print("\n" + "="*80)
    print(" "*25 + "🔍 WORKER QUEUE MONITOR")
    print("="*80)
    print("\nMonitoring backend at:", API_BASE)
    print("Press Ctrl+C to stop\n")
    
    # Clear screen on Windows/Unix
    if sys.platform == "win32":
        clear_cmd = "cls"
    else:
        clear_cmd = "clear"
    
    iteration = 0
    
    while True:
        try:
            status = await get_status()
            
            # Build display
            timestamp = datetime.now().strftime("%H:%M:%S")
            queue_size = status["queue_size"]
            busy = status["busy_workers"]
            idle = status["idle_workers"]
            total = status["total_workers"]
            
            # Print header every 20 iterations or on first run
            if iteration % 20 == 0:
                print("\n" + "="*80)
                print(f"{'Time':^10} | {'Queue':^8} | {'Workers':^20} | {'Worker Details':^30}")
                print("="*80)
            
            # Worker status
            worker_details = []
            for worker in sorted(status["workers"], key=lambda w: w["worker_id"]):
                wid = worker["worker_id"]
                wstatus = worker["status"]
                job_id = worker["current_job_id"]
                
                if wstatus == "busy" and job_id:
                    worker_details.append(f"W{wid}:Job{job_id}")
                else:
                    worker_details.append(f"W{wid}:Idle")
            
            workers_summary = f"{busy} busy / {idle} idle"
            workers_str = " | ".join(worker_details)
            
            # Queue visualization
            if queue_size > 0:
                queue_visual = f"{queue_size} jobs ⏳"
            else:
                queue_visual = "Empty ✓"
            
            print(f"{timestamp:^10} | {queue_visual:^8} | {workers_summary:^20} | {workers_str}")
            
            iteration += 1
            await asyncio.sleep(0.5)
            
        except httpx.ConnectError:
            print(f"\n❌ Cannot connect to {API_BASE}")
            print("Make sure backend is running: python start.py")
            break
        except KeyboardInterrupt:
            print("\n\n👋 Monitor stopped")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            await asyncio.sleep(2)


async def main():
    """Entry point."""
    # Test connection first
    try:
        status = await get_status()
        print(f"✅ Connected to backend")
        print(f"   Workers configured: {status['total_workers']}")
        print(f"   Current queue size: {status['queue_size']}")
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
        print(f"\nMake sure the backend is running:")
        print(f"  cd backend")
        print(f"  python start.py")
        return
    
    await monitor_loop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Exiting...")
