"""VendorShield FastAPI Backend.

AI-powered vendor risk assessment system using:
- LangChain/LangGraph for AI orchestration
- Groq (Llama 3.3 70B) for LLM inference
- BGE-large-en-v1.5 for embeddings (local)
- Pinecone for vector search
- MCP protocol for external AI agent integration

Serves both API and the React frontend from a single server.
"""

import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from routers import documents, assessments, controls, chat
from mcp.server import router as mcp_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Path to the built React frontend (one directory up → dist/)
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Starting VendorShield backend...")

    # Pre-load embedding model in background (non-blocking)
    try:
        from services.embedding import get_model
        get_model()  # Triggers download & load on first startup
        logger.info("Embedding model loaded.")
    except Exception as e:
        logger.warning(f"Embedding model pre-load failed (will retry on first use): {e}")

    # Check if frontend build exists
    if FRONTEND_DIR.exists():
        logger.info(f"Serving frontend from {FRONTEND_DIR}")
    else:
        logger.warning(
            f"Frontend build not found at {FRONTEND_DIR}. "
            "Run 'npm run build' in the project root to build the frontend."
        )

    logger.info("Server ready.")
    yield
    logger.info("Shutting down VendorShield backend.")


app = FastAPI(
    title="VendorShield API",
    description=(
        "AI-powered vendor risk assessment system. "
        "Compares vendor security/compliance documents against internal control checklist "
        "using RAG (Retrieval-Augmented Generation) with LangChain, Groq Llama, and Pinecone."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins (local-first application)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routers ──────────────────────────────────────────────────────────────
app.include_router(documents.router)
app.include_router(assessments.router)
app.include_router(controls.router)
app.include_router(chat.router)
app.include_router(mcp_router)


@app.get("/api/health", tags=["Health"])
async def health_check():
    return {"status": "healthy"}


@app.get("/api/info", tags=["Health"])
async def api_info():
    return {
        "service": "VendorShield API",
        "version": "1.0.0",
        "docs": "/docs",
        "mcp": "/mcp",
        "stack": {
            "llm": "Llama 3.3 70B (Groq)",
            "embeddings": "BGE-large-en-v1.5 (local, 1024 dim)",
            "vector_db": "Pinecone",
            "framework": "LangChain + LangGraph",
            "protocol": "MCP (Model Context Protocol)",
        },
    }


# ── Serve React Frontend (SPA) ──────────────────────────────────────────────
# Mount static assets (JS, CSS, images) from the Vite build
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="static")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(request: Request, full_path: str):
    """Catch-all: serve the React SPA for any non-API route."""
    # If the path maps to an actual file in dist/, serve it (e.g. favicon, robots.txt)
    file_path = FRONTEND_DIR / full_path
    if FRONTEND_DIR.exists() and file_path.exists() and file_path.is_file():
        return FileResponse(file_path)

    # Otherwise serve index.html (React Router handles client-side routing)
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)

    return {"message": "VendorShield API is running. Build the frontend with 'npm run build' to serve the UI."}
