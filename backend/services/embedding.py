"""Embedding service using Snowflake Arctic Embed (local, open-source)."""

from sentence_transformers import SentenceTransformer
from config import get_settings
import logging

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None


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
    """Generate embedding for a single text string."""
    model = get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def embed_batch(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """Generate embeddings for a batch of texts."""
    model = get_model()
    embeddings = model.encode(texts, normalize_embeddings=True, batch_size=batch_size)
    return embeddings.tolist()


def get_embedding_dimension() -> int:
    """Return the dimension of the embedding model."""
    return get_model().get_sentence_embedding_dimension()
