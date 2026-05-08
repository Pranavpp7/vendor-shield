"""Layer 7: VendorShield FastAPI Application — single entry point.

AI-powered vendor risk assessment system using:
- LangChain/LangGraph for AI orchestration
- OpenRouter (Llama 3.3 70B) for LLM inference
- BGE-large-en-v1.5 for embeddings (local)
- Qdrant for vector search (local Docker)
- MCP protocol for external AI agent integration

Serves both API and the React frontend from a single server.

RESPONSIBILITY:
    Creates the FastAPI app, mounts all routers, configures middleware,
    runs startup checks, and serves the React SPA.  No business logic.

IMPORTS FROM: routers/*, mcp/server, services/embedding, storage/*
IMPORTED BY:  uvicorn (the ASGI server)
"""

import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import get_settings
from routers import documents, assessments, controls, chat, email
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

    # 0. Auth sanity check — fail-loud if running without an API key
    if not get_settings().api_key:
        logger.warning(
            "=" * 70 + "\n"
            "  API_KEY is NOT set — auth is DISABLED. All endpoints are open.\n"
            "  This is OK for local development only. NEVER deploy like this.\n"
            "  Set API_KEY in your .env or environment to enable auth.\n"
            + "=" * 70
        )

    # 1. Initialize SQLite database (creates data/vendorshield.db + tables)
    try:
        from storage.local_store import init_db
        init_db()
        logger.info("SQLite database initialized.")
    except Exception as e:
        logger.warning(f"Database init failed: {e}")

    # 2. Pre-load embedding model (triggers download on first run)
    try:
        from services.embedding import get_model
        get_model()
        logger.info("Embedding model loaded.")
    except Exception as e:
        logger.warning(f"Embedding model pre-load failed (will retry on first use): {e}")

    # 3. Check Qdrant connectivity
    try:
        from storage.qdrant_store import _get_client
        _get_client()
        logger.info("Qdrant connection verified.")
    except Exception as e:
        logger.warning(
            f"Qdrant not reachable (start with: docker-compose up -d): {e}"
        )

    # 4. Check if frontend build exists
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

    # Close the pooled MCP HTTP client if it was created.
    try:
        from chains.assessment_graph import _mcp_client
        if _mcp_client is not None:
            await _mcp_client.aclose()
    except Exception as e:
        logger.warning(f"MCP client shutdown failed: {e}")


app = FastAPI(
    title="VendorShield API",
    description=(
        "AI-powered vendor risk assessment system. "
        "Compares vendor security/compliance documents against internal control checklist "
        "using RAG (Retrieval-Augmented Generation) with LangChain, OpenRouter Llama, and Qdrant."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
raw_origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]
allow_origins = ["*"] if "*" in raw_origins else raw_origins

# CORS origins come from config/env for safer deployment defaults.
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins or ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routers ──────────────────────────────────────────────────────────────
app.include_router(documents.router)
app.include_router(assessments.router)
app.include_router(assessments.vendors_router)
app.include_router(controls.router)
app.include_router(chat.router)
app.include_router(email.router)
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
            "llm": "Llama 3.3 70B (OpenRouter)",
            "embeddings": "BGE-large-en-v1.5 (local, 1024 dim)",
            "vector_db": "Qdrant (local Docker)",
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
