"""
VendorShield Startup Script

Builds the React frontend and starts the FastAPI server.

Usage:
    uv run start.py              # Build frontend + start (production)
    uv run start.py --dev        # Skip build, start with hot-reload (development)
    uv run start.py --skip-build # Skip build, start without hot-reload
"""

import subprocess
import sys
import os
from pathlib import Path

# Must add backend/ to sys.path so `from config import get_settings` works
# regardless of where the user invokes this script from.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import get_settings

ROOT_DIR = Path(__file__).resolve().parent.parent  # project root
BACKEND_DIR = Path(__file__).resolve().parent       # backend/
DIST_DIR = ROOT_DIR / "dist"

DEV_MODE = "--dev" in sys.argv
SKIP_BUILD = "--skip-build" in sys.argv or DEV_MODE


def build_frontend():
    """Build the React frontend using npm."""
    if not (ROOT_DIR / "package.json").exists():
        print("No package.json found — skipping frontend build.")
        return

    if not (ROOT_DIR / "node_modules").exists():
        print("Installing frontend dependencies...")
        subprocess.run(["npm", "install"], cwd=str(ROOT_DIR), check=True, shell=True)

    print("Building frontend...")
    subprocess.run(["npm", "run", "build"], cwd=str(ROOT_DIR), check=True, shell=True)

    if DIST_DIR.exists():
        print(f"Frontend built → {DIST_DIR}")
    else:
        print("Frontend build completed but dist/ not found.")


def start_server(reload: bool = False):
    """Start the FastAPI server with uvicorn."""
    settings = get_settings()
    port = settings.server_port
    mode = "development (hot-reload)" if reload else "production"
    print(f"Starting VendorShield [{mode}] on http://localhost:{port}")
    print(f"API docs: http://localhost:{port}/docs")
    print("─" * 50)

    import uvicorn
    os.chdir(str(BACKEND_DIR))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=reload)


if __name__ == "__main__":
    if SKIP_BUILD:
        print("Skipping frontend build.")
    else:
        build_frontend()

    start_server(reload=DEV_MODE)
