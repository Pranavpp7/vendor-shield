"""
Layer 3: Text Embedding using sentence-transformers.

RESPONSIBILITY:
    Converts text into 1024-dimensional vectors using BGE-large-en-v1.5.
    Runs 100% locally — no API key, no network call after initial download.
    That is all.  No chunking, no database calls.

    The model is loaded once and cached for the lifetime of the process.
    GPU is auto-detected and used if available (CUDA or MPS).

    BGE models require a special prefix for search queries but NOT for
    document passages.  This is handled automatically:
    - embed_query()  → adds prefix (for search)
    - embed_chunks() → no prefix (for document storage)

IMPORTS FROM: config.py (for embedding_model name)
IMPORTED BY:  services/ingestion.py, services/retrieval.py
"""

import logging
import torch
from sentence_transformers import SentenceTransformer
from config import get_settings

logger = logging.getLogger(__name__)

# Singleton model instance — loaded once on first use
_model: SentenceTransformer | None = None

# BGE models expect this prefix on search queries to improve relevance.
# Document passages are embedded WITHOUT the prefix.
_BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def get_model() -> SentenceTransformer:
    """Load and cache the embedding model.

    Auto-detects the best available device:
    - CUDA GPU (NVIDIA)
    - MPS (Apple Silicon)
    - CPU (fallback)

    Call this at startup to pre-load the model so the first user
    request doesn't have to wait for the ~1GB download.
    """
    global _model
    if _model is not None:
        return _model

    settings = get_settings()

    # Pick the best available device
    if torch.cuda.is_available():
        device = "cuda"
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"

    logger.info(
        f"Loading embedding model '{settings.embedding_model}' on {device}..."
    )
    _model = SentenceTransformer(settings.embedding_model, device=device)
    logger.info(
        f"Model loaded. Dimension: {_model.get_sentence_embedding_dimension()}"
    )
    return _model


def embed_query(text: str) -> list[float]:
    """Embed a search query into a 1024-dim vector.

    Adds the BGE query prefix automatically.  Use this for all search
    queries (control search_query, user chat questions, etc.).

    Args:
        text: The search query string.

    Returns:
        A single 1024-dimensional vector as a list of floats.
    """
    model = get_model()
    prefixed = _BGE_QUERY_PREFIX + text
    vector = model.encode(prefixed, normalize_embeddings=True)
    return vector.tolist()


def embed_chunks(texts: list[str]) -> list[list[float]]:
    """Embed a batch of document chunks into 1024-dim vectors.

    No query prefix — these are passages, not search queries.
    Uses batch encoding for efficiency.

    Args:
        texts: List of text chunks to embed.

    Returns:
        List of 1024-dimensional vectors, one per input chunk.
        Returns empty list if input is empty.
    """
    if not texts:
        return []

    model = get_model()
    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=len(texts) > 50,
        batch_size=32,
    )
    logger.info(f"Embedded {len(texts)} chunks")
    return vectors.tolist()
