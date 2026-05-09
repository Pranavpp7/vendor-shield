"""
Layer 2a: Qdrant Vector Database Operations.

RESPONSIBILITY:
    Raw vector database operations only — create collections, add vectors,
    search vectors, delete collections. No business logic, no text processing,
    no embedding. Just Qdrant CRUD.

    Each assessment gets its own Qdrant collection named "vendorshield_{assessment_id}"
    so vendor data is completely isolated between assessments.

    Qdrant runs locally via Docker on port 6333 — no cloud, no API key needed.
    Install: pip install qdrant-client
    Start:   docker-compose up -d  (or: docker run -p 6333:6333 qdrant/qdrant)

IMPORTS FROM: config.py (for qdrant_host, qdrant_port, embedding_dimensions)
IMPORTED BY:  services/ingestion.py, services/retrieval.py, mcp/server.py
"""

import logging
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from config import get_settings

logger = logging.getLogger(__name__)

_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    """Return a singleton Qdrant client, creating it on first call.

    Connects to the local Qdrant Docker container — no API key needed.
    Raises a clear error if Qdrant is not reachable.
    """
    global _client
    if _client is None:
        settings = get_settings()
        try:
            _client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
            )
            # Verify connectivity with a lightweight call
            _client.get_collections()
            logger.info(
                f"Connected to Qdrant at {settings.qdrant_host}:{settings.qdrant_port}"
            )
        except Exception as e:
            _client = None
            raise ConnectionError(
                f"Cannot connect to Qdrant at {settings.qdrant_host}:{settings.qdrant_port}. "
                f"Is Docker running? Start it with: docker-compose up -d\n"
                f"Error: {e}"
            ) from e
    return _client


def _collection_name(assessment_id: str) -> str:
    """Build the Qdrant collection name for an assessment.

    Format: vendorshield_{assessment_id}
    Each assessment is fully isolated in its own collection.
    """
    return f"vendorshield_{assessment_id}"


# ---------------------------------------------------------------------------
# Collection management
# ---------------------------------------------------------------------------


def collection_exists(assessment_id: str) -> bool:
    """Check whether a collection exists for this assessment."""
    client = _get_client()
    name = _collection_name(assessment_id)
    try:
        collections = client.get_collections().collections
        return any(c.name == name for c in collections)
    except Exception as e:
        logger.error(f"Error checking collection {name}: {e}")
        raise


def create_collection(assessment_id: str) -> None:
    """Create a Qdrant collection for this assessment.

    Uses 1024-dimension vectors (matching BGE-large-en-v1.5) with
    cosine distance. Skips creation if the collection already exists.
    """
    name = _collection_name(assessment_id)

    if collection_exists(assessment_id):
        logger.info(f"Collection {name} already exists, skipping creation")
        return

    client = _get_client()
    settings = get_settings()

    try:
        client.create_collection(
            collection_name=name,
            vectors_config=qdrant_models.VectorParams(
                size=settings.embedding_dimensions,  # 1024 for BGE-large
                distance=qdrant_models.Distance.COSINE,
            ),
        )
        logger.info(
            f"Created collection {name} "
            f"(dims={settings.embedding_dimensions}, distance=cosine)"
        )
    except Exception as e:
        logger.error(f"Error creating collection {name}: {e}")
        raise


def delete_collection(assessment_id: str) -> None:
    """Delete the entire collection for this assessment.

    No-op if the collection does not exist.
    """
    name = _collection_name(assessment_id)

    if not collection_exists(assessment_id):
        logger.info(f"Collection {name} does not exist, nothing to delete")
        return

    client = _get_client()
    try:
        client.delete_collection(collection_name=name)
        logger.info(f"Deleted collection {name}")
    except Exception as e:
        logger.error(f"Error deleting collection {name}: {e}")
        raise


# ---------------------------------------------------------------------------
# Vector operations
# ---------------------------------------------------------------------------


def add_chunks(
    assessment_id: str,
    chunks: list[str],
    vectors: list[list[float]],
    document_name: str,
) -> int:
    """Add text chunks and their embeddings to the assessment's collection.

    Args:
        assessment_id: Which assessment this data belongs to.
        chunks: List of plain text strings (the chunk content).
        vectors: List of 1024-dim embedding vectors, one per chunk.
        document_name: Source filename or URL — stored in payload for citations.

    Returns:
        Number of vectors successfully added.

    IDs are deterministic: "{assessment_id}_{document_name}_{chunk_index}"
    so re-ingesting the same document overwrites rather than duplicates.
    """
    if not chunks:
        return 0

    if len(chunks) != len(vectors):
        raise ValueError(
            f"Mismatch: {len(chunks)} chunks but {len(vectors)} vectors"
        )

    name = _collection_name(assessment_id)

    # Ensure the collection exists before adding data
    create_collection(assessment_id)

    client = _get_client()

    # Build point objects with payload
    points = []
    for i, (chunk_text, vector) in enumerate(zip(chunks, vectors)):
        # Deterministic ID so re-ingestion overwrites, not duplicates
        point_id = abs(hash(f"{assessment_id}_{document_name}_{i}")) % (2**63)
        points.append(
            qdrant_models.PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "content": chunk_text[:4000],  # cap payload size
                    "document_name": document_name,
                    "chunk_index": i,
                },
            )
        )

    # Upsert in batches of 100
    batch_size = 100
    for start in range(0, len(points), batch_size):
        batch = points[start : start + batch_size]
        try:
            client.upsert(collection_name=name, points=batch)
        except Exception as e:
            logger.error(
                f"Error upserting batch {start}-{start + len(batch)} "
                f"into {name}: {e}"
            )
            raise

    logger.info(
        f"Added {len(points)} vectors to {name} from document '{document_name}'"
    )
    return len(points)


def delete_document_vectors(assessment_id: str, document_name: str) -> None:
    """Delete all vectors belonging to a specific document within an assessment.

    Uses a payload filter on the document_name field.  Called when a document
    is deleted so its chunks no longer appear in retrieval results.
    """
    name = _collection_name(assessment_id)

    if not collection_exists(assessment_id):
        logger.info(f"Collection {name} does not exist, nothing to delete")
        return

    client = _get_client()
    try:
        client.delete(
            collection_name=name,
            points_selector=qdrant_models.FilterSelector(
                filter=qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="document_name",
                            match=qdrant_models.MatchValue(value=document_name),
                        )
                    ]
                )
            ),
        )
        logger.info(f"Deleted vectors for '{document_name}' from {name}")
    except Exception as e:
        logger.error(f"Error deleting vectors for '{document_name}' from {name}: {e}")
        raise


def similarity_search(
    assessment_id: str,
    query_vector: list[float],
    top_k: int = 8,
) -> list[dict]:
    """Search for the most similar chunks in an assessment's collection.

    Args:
        assessment_id: Which assessment to search.
        query_vector: 1024-dim embedding of the search query.
        top_k: Maximum number of results to return.

    Returns:
        List of dicts, each containing:
        - "content": the chunk text
        - "document_name": source file name (for citations)
        - "chunk_index": position within the source document
        - "score": cosine similarity score (0.0 to 1.0)

        Results are sorted by score descending (most relevant first).
        Returns empty list if collection does not exist.
    """
    name = _collection_name(assessment_id)

    if not collection_exists(assessment_id):
        logger.warning(f"Collection {name} does not exist, returning empty results")
        return []

    client = _get_client()

    try:
        results = client.query_points(
            collection_name=name,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )
    except Exception as e:
        logger.error(f"Error searching {name}: {e}")
        raise

    matches = []
    for point in results.points:
        payload = point.payload or {}
        matches.append({
            "content": payload.get("content", ""),
            "document_name": payload.get("document_name", ""),
            "chunk_index": payload.get("chunk_index", 0),
            "score": point.score,
        })

    return matches
