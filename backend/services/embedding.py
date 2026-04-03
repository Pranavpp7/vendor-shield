"""Embedding service using BGE-large-en-v1.5 (local, open-source).

BGE models achieve best retrieval quality when queries are prefixed with
an instruction. Document passages are embedded without a prefix.
"""

from sentence_transformers import SentenceTransformer
from config import get_settings
import logging

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None

# BGE retrieval instruction prefix (improves query-document matching)
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def get_model() -> SentenceTransformer:
    """Lazy-load the embedding model (cached after first call)."""
    global _model
    if _model is None:
        settings = get_settings()
        logger.info(f"Loading embedding model: {settings.embedding_model}")
        _model = SentenceTransformer(settings.embedding_model)
        logger.info(f"Model loaded. Dimension: {_model.get_sentence_embedding_dimension()}")
    return _model


def embed_text(text: str) -> list[float]:
    """Generate embedding for a query string (with BGE instruction prefix)."""
    model = get_model()
    embedding = model.encode(BGE_QUERY_PREFIX + text, normalize_embeddings=True)
    return embedding.tolist()


def embed_passage(text: str) -> list[float]:
    """Generate embedding for a document passage (no prefix)."""
    model = get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def embed_batch(texts: list[str], batch_size: int = 32, is_query: bool = False) -> list[list[float]]:
    """Generate embeddings for a batch of texts.

    Args:
        texts: List of text strings to embed.
        batch_size: Batch size for encoding.
        is_query: If True, prepend BGE query prefix (for search queries).
                  If False, embed as document passages (for indexing).
    """
    model = get_model()
    if is_query:
        texts = [BGE_QUERY_PREFIX + t for t in texts]
    embeddings = model.encode(texts, normalize_embeddings=True, batch_size=batch_size)
    return embeddings.tolist()


def get_embedding_dimension() -> int:
    """Return the dimension of the embedding model."""
    return get_model().get_sentence_embedding_dimension()
