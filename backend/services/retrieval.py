"""
Layer 3: Document Retrieval (Semantic Search).

RESPONSIBILITY:
    Takes a text query, embeds it, and searches the assessment's Qdrant
    collection for the most similar document chunks.  Returns results
    with source document names so evaluation.py can build citations.

    This is intentionally a thin wrapper around embedding + qdrant_store.
    The value is a single clean interface for callers — they don't need
    to know about embedding or Qdrant separately.  Also makes it easy
    to swap to hybrid search later without changing callers.

IMPORTS FROM: services/embedding, storage/qdrant_store
IMPORTED BY:  services/evaluation.py, services/chat.py, mcp/server.py
"""

import logging
from services.embedding import embed_query
from storage.qdrant_store import similarity_search

logger = logging.getLogger(__name__)


def search_documents(
    query: str,
    assessment_id: str,
    top_k: int = 8,
) -> list[dict]:
    """Search an assessment's documents for chunks matching a query.

    Args:
        query: Natural language search text (e.g. a control's search_query
               or a user's chat question).
        assessment_id: Which assessment's documents to search.
        top_k: Maximum number of results to return.

    Returns:
        List of dicts sorted by relevance (most relevant first), each with:
        - "content": the chunk text
        - "document_name": source filename or URL (for citations)
        - "chunk_index": position within the source document
        - "score": cosine similarity score (0.0 to 1.0)

        Returns empty list if no collection exists or no matches found.
    """
    # 1. Embed the query (with BGE search prefix)
    query_vector = embed_query(query)

    # 2. Search Qdrant
    results = similarity_search(assessment_id, query_vector, top_k)

    logger.info(
        f"Retrieved {len(results)} chunks for query "
        f"(assessment={assessment_id}, top_k={top_k})"
    )
    return results
