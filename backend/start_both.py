#!/usr/bin/env python3
"""
Simple script to start both FastAPI and Socket.IO servers
"""
import subprocess
import sys
import os
import time
import signal
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print("\n🛑 Shutting down servers...")
    sys.exit(0)

if __name__ == "__main__":
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("🎯 Starting both FastAPI and Socket.IO servers...")
    print("📡 FastAPI will run on port 3001")
    print("🔌 Socket.IO will run on port 3002")
    print("Press Ctrl+C to stop both servers")
    print("-" * 50)
    
    try:
        # Start FastAPI server
        print("🚀 Starting FastAPI server...")
        fastapi_process = subprocess.Popen([
            sys.executable, "-m", "uvicorn", "main:app", 
            "--host", "0.0.0.0", "--port", "3001", "--reload"
        ], cwd=os.path.dirname(os.path.abspath(__file__)))
        
        # Wait a moment for FastAPI to start
        time.sleep(3)
        
        # Start Socket.IO server
        print("🔌 Starting Socket.IO server...")
        socket_process = subprocess.Popen([
            sys.executable, "socket_server.py"
        ], cwd=os.path.dirname(os.path.abspath(__file__)))
        
        print("✅ Both servers started successfully!")
        print("📡 FastAPI: http://localhost:3001")
        print("🔌 Socket.IO: http://localhost:3002")
        
        # Wait for both processes
        try:
            fastapi_process.wait()
        except KeyboardInterrupt:
            print("\n🛑 Shutting down servers...")
            fastapi_process.terminate()
            socket_process.terminate()
            fastapi_process.wait()
            socket_process.wait()
            print("✅ Servers stopped")
            
    except Exception as e:
        print(f"❌ Error starting servers: {e}")
        if 'fastapi_process' in locals():
            fastapi_process.terminate()
        if 'socket_process' in locals():
            socket_process.terminate()
