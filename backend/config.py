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

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):

    # ── OpenRouter LLM ───────────────────────────────────────────────────────
    # OpenRouter provides a unified API for many open-source models.
    # Get your API key at https://openrouter.ai/keys
    openrouter_api_key: str = ""
    # OpenRouter is OpenAI-compatible — point the OpenAI SDK at this URL.
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Model ID as it appears on OpenRouter.  ~$0.006 per 20-control
    # assessment at current pricing — the eval-gated, verified default.
    #
    # Model changes MUST pass the eval gate first:
    #     uv run python evals/run_evals.py
    # Eval-gate history (don't retry these without new evidence):
    #   - openai/gpt-oss-120b:free  → REJECTED 19/30 (malformed/truncated JSON)
    #   - this model's ":free" tag  → REJECTED 19/30 (free-tier rate limits
    #     exhaust retries under concurrent runs; fine for light manual use
    #     with LLM_CONCURRENCY=1, unreliable for full assessments)
    # For a true $0 setup, run a local model via Ollama and point
    # OPENROUTER_BASE_URL at http://localhost:11434/v1.
    openrouter_model: str = "meta-llama/llama-3.3-70b-instruct"
    # Max concurrent LLM calls during an assessment run.  Higher = faster
    # runs but more likely to hit provider rate limits (free tiers are
    # stricter — the client retries 429s with backoff automatically).
    llm_concurrency: int = 4
    # USD per million tokens — used to estimate per-run cost shown in the UI.
    # Defaults track meta-llama/llama-3.3-70b-instruct; set to 0 for
    # :free models or local Ollama.
    llm_price_in_per_m: float = 0.12
    llm_price_out_per_m: float = 0.30

    # ── Fallback LLM provider (automatic failover) ───────────────────────────
    # Used only when the PRIMARY provider is dead for account/model reasons
    # (402 insufficient credits, 401, 404/410 model gone) — never for
    # transient 429/5xx.  Defaults target Groq's OpenAI-compatible API,
    # whose FREE tier hosts llama-3.3-70b-versatile and openai/gpt-oss-120b
    # (get a key at https://console.groq.com/keys).  Empty key = disabled.
    # Any fallback model must pass the eval gate before you rely on it.
    fallback_base_url: str = "https://api.groq.com/openai/v1"
    fallback_api_key: str = ""
    fallback_model: str = "llama-3.3-70b-versatile"

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

    # ── Review & Evidence Quality ────────────────────────────────────────────
    # Controls whose LLM confidence falls below this threshold are flagged
    # needs_review so an analyst confirms or overrides the score.
    review_confidence_threshold: float = 0.5
    # Documents uploaded more than this many days ago are flagged as stale
    # evidence (e.g. a SOC 2 report is reissued annually).
    evidence_stale_days: int = 365

    # ── Local Data Storage ───────────────────────────────────────────────────
    # All structured data (assessments, chat history, document metadata)
    # is stored in a single SQLite database file (vendorshield.db) under this
    # folder.  No Supabase, no Postgres — just a local .db file.
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
    # Port uvicorn listens on (reads from SERVER_PORT env var).
    server_port: int = 8000
    # Comma-separated list of allowed CORS origins.
    # Use "*" only for local experimentation.
    cors_allow_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ── Resend (for emailing PDF reports) ────────────────────────────────────
    # Get your free API key at https://resend.com
    # Free tier sends from onboarding@resend.dev — no custom domain needed.
    resend_api_key: str = ""

    # ── Clerk Authentication ─────────────────────────────────────────────────
    # JWKS endpoint for verifying Clerk-issued JWTs.
    # Found in Clerk Dashboard → API Keys → Advanced → JWKS URL.
    # Empty string = dev mode: auth is skipped, all data is visible.
    clerk_jwks_url: str = ""

    # ── API Key (single-tenant shared-secret auth) ───────────────────────────
    # When set (and Clerk is not configured), every /api and /mcp request
    # must send X-API-Key: <this value>.  Empty string = dev mode (open).
    api_key: str = ""

    # ── Chat memory ──────────────────────────────────────────────────────────
    # SHORT-TERM: how many recent chat messages (user + assistant combined)
    # are replayed into the model's context each turn, so follow-up
    # questions ("what about the second one?") resolve correctly.
    chat_history_window: int = 10
    # LONG-TERM: mem0-backed analyst memory.  Durable facts an analyst
    # establishes in chat ("we require SOC 2 Type II from payment vendors")
    # are extracted by the LLM, embedded with the local BGE model, stored
    # in Qdrant (collection "vendorshield_memories"), and recalled
    # semantically in later chats across ALL assessments.  Requires the
    # mem0ai package; degrades silently to off when unavailable.
    memory_enabled: bool = True

    # ── Langfuse (optional LLM observability) ────────────────────────────────
    # Free cloud tier at https://cloud.langfuse.com — create a project and
    # paste its API keys here.  When both keys are set (and the langfuse
    # package is installed), every LLM call is traced with latency, tokens,
    # and cost, and each assessment run renders as one nested trace.
    # Both keys empty = tracing fully disabled: no import, no network.
    # NOTE: these are LANGFUSE_* vars — NOT the api_key field above, which
    # is VendorShield's own auth tier.
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # ── Demo mode (free read-only hosting) ───────────────────────────────────
    # When true, all mutating requests (POST/PUT/PATCH/DELETE) to /api and
    # /mcp return 403 — the app serves seeded data read-only with zero LLM
    # spend possible.  Built for free-tier hosting (e.g. HF Spaces).
    demo_mode: bool = False

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
