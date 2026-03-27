"""
VendorShield Startup Script

Builds the React frontend and starts the FastAPI server.
Single command: uv run start.py
"""

import subprocess
import sys
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent  # project root
BACKEND_DIR = Path(__file__).resolve().parent       # backend/
DIST_DIR = ROOT_DIR / "dist"


def build_frontend():
    """Build the React frontend using npm."""
    if not (ROOT_DIR / "package.json").exists():
        print("⚠  No package.json found — skipping frontend build.")
        return

    # Check if node_modules exists
    if not (ROOT_DIR / "node_modules").exists():
        print("📦 Installing frontend dependencies...")
        subprocess.run(["npm", "install"], cwd=str(ROOT_DIR), check=True, shell=True)

    print("🔨 Building frontend...")
    subprocess.run(["npm", "run", "build"], cwd=str(ROOT_DIR), check=True, shell=True)

    if DIST_DIR.exists():
        print(f"✅ Frontend built → {DIST_DIR}")
    else:
        print("⚠  Frontend build completed but dist/ not found.")


def start_server():
    """Start the FastAPI server with uvicorn."""
    print("🚀 Starting VendorShield server on http://localhost:8000")
    print("📄 API docs at http://localhost:8000/docs")
    print("🌐 App UI at http://localhost:8000")
    print("─" * 50)

    import uvicorn
    os.chdir(str(BACKEND_DIR))
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    # Skip frontend build if --skip-build flag is passed
    if "--skip-build" not in sys.argv:
        build_frontend()
    else:
        print("⏭  Skipping frontend build (--skip-build)")

    start_server()
