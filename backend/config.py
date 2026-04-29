"""
Layer 1: Configuration — Single source of truth for all settings.

RESPONSIBILITY:
    This file holds every configurable value in the entire backend.
    Nothing else in the codebase should contain hardcoded API keys,
    folder paths, model names, port numbers, or other settings.
    Everything reads from here.

HOW IT WORKS:
    Uses pydantic BaseSettings so values can come from either:
    1. A .env file in the backend/ directory (for local development)
    2. Real environment variables (for deployment)
    pydantic automatically reads both and environment variables
    take precedence over .env file values.

IMPORTS FROM: nothing (this is the bottom of the dependency chain)
IMPORTED BY:  every other layer — services, storage, mcp, agent, routers, main
"""

from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):

    # ── Groq LLM ─────────────────────────────────────────────────────────────
    # Groq provides fast inference for open-source models.
    # Get your free API key at https://console.groq.com
    # This key is the ONLY paid/external API the backend needs.
    groq_api_key: str = ""
    # Which model to use on Groq.  llama-3.3-70b-versatile is the best
    # balance of quality and speed for structured JSON output.
    groq_model: str = "llama-3.3-70b-versatile"

    # ── Qdrant Vector Database ───────────────────────────────────────────────
    # Qdrant runs locally via Docker — no cloud, no API key needed.
    # Start it with:  docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
    # Dashboard:      http://localhost:6333/dashboard
    # The host and port where the Qdrant Docker container is listening.
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # ── Embedding Model ──────────────────────────────────────────────────────
    # BGE-large-en-v1.5 from HuggingFace, runs 100% locally on CPU or GPU.
    # No API key, no network call after the initial model download.
    # The model name as it appears on HuggingFace (used by sentence-transformers).
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    # Output vector size — must match the model's native dimension.
    # BGE-large-en-v1.5 always outputs 1024-dim vectors.
    # Qdrant collections are created with this dimension.
    embedding_dimensions: int = 1024

    # ── Chunking ─────────────────────────────────────────────────────────────
    # How to split documents before embedding them.
    # Chunk size in number of words (not characters).
    chunk_size: int = 500
    # Overlap in words between consecutive chunks.
    # Overlap ensures that sentences sitting on a chunk boundary
    # aren't cut in half and lost to retrieval.
    chunk_overlap: int = 50

    # ── Retrieval ────────────────────────────────────────────────────────
    # Number of document chunks returned per control during evaluation.
    # Lower = fewer tokens sent to the LLM (faster, cheaper).
    # Higher = more evidence surface (better recall, more tokens).
    retrieval_top_k: int = 3

    # ── Local Data Storage ───────────────────────────────────────────────────
    # All structured data (assessments, chat history, document metadata)
    # is stored as JSON files under this folder.  No Supabase, no Postgres.
    # Path is relative to the backend/ directory.
    data_dir: str = "data"
    # Uploaded files are saved here before being processed.
    upload_dir: str = "data/uploads"

    # ── MCP (Model Context Protocol) ─────────────────────────────────────────
    # The MCP server runs as part of this FastAPI app at /mcp.
    # The MCP client connects to it at this URL.
    # In production you could point this at a remote MCP server instead.
    mcp_server_url: str = "http://localhost:8000/mcp"

    # ── Server ───────────────────────────────────────────────────────────────
    # Port that the FastAPI server listens on.
    server_port: int = 8000
    # Path to the built React frontend (relative to project root).
    # After running `npm run build`, the output lands in dist/.
    frontend_dir: str = "../dist"
    # Comma-separated list of allowed CORS origins.
    # Use "*" only for local experimentation.
    cors_allow_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ── Resend (for emailing PDF reports) ────────────────────────────────────
    # Get your free API key at https://resend.com
    # Free tier sends from onboarding@resend.dev — no custom domain needed.
    resend_api_key: str = ""

    # ── pydantic-settings config ─────────────────────────────────────────────
    model_config = {
        # Load values from a .env file sitting next to this config.py
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        # If a field appears in both .env and the real environment,
        # the real environment variable wins.
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """Return the singleton Settings instance.

    lru_cache ensures we only read .env once.  Every caller gets
    the same object so there's no risk of inconsistent config.
    """
    return Settings()
