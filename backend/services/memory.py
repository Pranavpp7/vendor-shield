"""
Layer 3: Long-term analyst memory — mem0 over the existing stack.

RESPONSIBILITY:
    Cross-assessment memory for the chat assistant.  Durable facts an
    analyst establishes in one conversation ("we require SOC 2 Type II
    from all payment vendors") are extracted by mem0's LLM pass, embedded
    with the SAME local BGE model used for documents, stored in the SAME
    Qdrant instance (collection "vendorshield_memories"), and recalled
    semantically in later chats — across assessments.  No new services,
    no new keys, no extra cost beyond the extraction LLM call.

    Distinct from the two other context layers:
      - SHORT-TERM memory = the windowed conversation history that
        routers/chat.py replays into the prompt (this turn's dialogue)
      - RAG retrieval = vendor documents, the ONLY source of vendor facts
    Memories carry the ANALYST's organizational context — they are never
    treated as evidence about a vendor.

    Enabled iff settings.memory_enabled AND the mem0ai package imports.
    Every public function degrades to a no-op on any failure — a memory
    outage must never break chat.

IMPORTS FROM: config
IMPORTED BY:  routers/chat.py
"""

import logging
import os

from config import get_settings

logger = logging.getLogger(__name__)

MEMORY_COLLECTION = "vendorshield_memories"

_memory = None
_disabled = False  # sticky once init fails or the feature is off


def _client():
    """Lazily build the mem0 Memory singleton; None when unavailable."""
    global _memory, _disabled
    if _disabled:
        return None
    if _memory is not None:
        return _memory

    s = get_settings()
    if not s.memory_enabled:
        _disabled = True
        return None

    os.environ.setdefault("MEM0_TELEMETRY", "False")
    try:
        from mem0 import Memory

        _memory = Memory.from_config({
            "llm": {
                "provider": "openai",
                "config": {
                    "model": s.openrouter_model,
                    "api_key": s.openrouter_api_key,
                    "openai_base_url": s.openrouter_base_url,
                    "temperature": 0.0,
                    "max_tokens": 1024,
                },
            },
            "embedder": {
                "provider": "huggingface",
                "config": {"model": s.embedding_model},
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "host": s.qdrant_host,
                    "port": s.qdrant_port,
                    "collection_name": MEMORY_COLLECTION,
                    "embedding_model_dims": s.embedding_dimensions,
                },
            },
        })
        logger.info(
            f"mem0 long-term memory enabled (Qdrant collection {MEMORY_COLLECTION})"
        )
        return _memory
    except Exception as e:
        logger.warning(f"mem0 unavailable — long-term memory disabled: {e}")
        _disabled = True
        return None


def _scope(user_id: str) -> str:
    """Dev mode / single-tenant auth yields '' — give memories a stable owner."""
    return user_id or "default-analyst"


def recall(user_id: str, query: str, limit: int = 5) -> list[str]:
    """Semantic search of the analyst's memories.  [] on any failure."""
    m = _client()
    if m is None:
        return []
    try:
        try:
            # mem0 ≥2.x: scoping moved into filters
            raw = m.search(query, filters={"user_id": _scope(user_id)}, limit=limit)
        except Exception:
            # mem0 1.x signature
            raw = m.search(query, user_id=_scope(user_id), limit=limit)
        hits = raw.get("results", []) if isinstance(raw, dict) else raw
        return [h["memory"] for h in hits
                if isinstance(h, dict) and h.get("memory")]
    except Exception as e:
        logger.warning(f"memory recall failed: {e}")
        return []


def remember(user_id: str, question: str, answer: str) -> None:
    """Extract and store durable facts from one exchange.  Never raises.

    mem0 runs an LLM pass that decides what (if anything) is worth
    keeping — most exchanges add nothing, and that's correct.
    """
    m = _client()
    if m is None:
        return
    try:
        m.add(
            [
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ],
            user_id=_scope(user_id),
        )
    except Exception as e:
        logger.warning(f"memory store failed: {e}")


def reset_memory() -> None:
    """Drop the singleton and the sticky-disabled flag (tests, settings)."""
    global _memory, _disabled
    _memory = None
    _disabled = False
