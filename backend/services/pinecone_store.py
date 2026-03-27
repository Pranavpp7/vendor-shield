"""Pinecone vector store operations."""

from pinecone import Pinecone, ServerlessSpec
from config import get_settings
from services.chunking import Chunk
from services.embedding import embed_text, embed_batch
import logging

logger = logging.getLogger(__name__)

_pc: Pinecone | None = None
_index = None


def get_pinecone_client() -> Pinecone:
    global _pc
    if _pc is None:
        settings = get_settings()
        _pc = Pinecone(api_key=settings.pinecone_api_key)
    return _pc


def get_index():
    """Get or create the Pinecone index."""
    global _index
    if _index is not None:
        return _index

    settings = get_settings()
    pc = get_pinecone_client()

    # Create index if it doesn't exist
    existing = [idx.name for idx in pc.list_indexes()]
    if settings.pinecone_index_name not in existing:
        logger.info(f"Creating Pinecone index: {settings.pinecone_index_name}")
        pc.create_index(
            name=settings.pinecone_index_name,
            dimension=settings.embedding_dimensions,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )

    _index = pc.Index(settings.pinecone_index_name)
    return _index


def upsert_chunks(
    assessment_id: str,
    vendor_name: str,
    document_name: str,
    chunks: list[Chunk],
    document_id: str = "",
) -> int:
    """Embed chunks and upsert them into Pinecone under the assessment namespace."""
    if not chunks:
        return 0

    index = get_index()

    # Batch embed all chunk contents
    texts = [c.content for c in chunks]
    embeddings = embed_batch(texts)

    # Build vectors with metadata
    vectors = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        vector_id = f"{assessment_id}_{document_id}_{chunk.chunk_index}"
        vectors.append({
            "id": vector_id,
            "values": embedding,
            "metadata": {
                "content": chunk.content[:4000],  # Pinecone metadata limit
                "vendor_name": vendor_name,
                "document_name": chunk.source,
                "document_id": document_id,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index,
            },
        })

    # Upsert in batches of 100 (Pinecone limit)
    for i in range(0, len(vectors), 100):
        batch = vectors[i: i + 100]
        index.upsert(vectors=batch, namespace=assessment_id)

    logger.info(f"Upserted {len(vectors)} vectors for assessment={assessment_id}, doc={document_name}")
    return len(vectors)


def search(
    assessment_id: str,
    query: str,
    top_k: int = 8,
) -> list[dict]:
    """Semantic search within an assessment's namespace."""
    index = get_index()
    query_embedding = embed_text(query)

    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        namespace=assessment_id,
        include_metadata=True,
    )

    matches = []
    for match in results.get("matches", []):
        matches.append({
            "id": match["id"],
            "score": match["score"],
            "content": match["metadata"].get("content", ""),
            "document_name": match["metadata"].get("document_name", ""),
            "document_id": match["metadata"].get("document_id", ""),
            "page_number": match["metadata"].get("page_number", 0),
            "chunk_index": match["metadata"].get("chunk_index", 0),
        })

    return matches


def delete_by_assessment(assessment_id: str):
    """Delete all vectors for an assessment."""
    index = get_index()
    index.delete(delete_all=True, namespace=assessment_id)
    logger.info(f"Deleted all vectors for assessment={assessment_id}")


def delete_by_document(assessment_id: str, document_id: str):
    """Delete vectors for a specific document within an assessment."""
    index = get_index()
    # Use metadata filter to find vectors for this document
    # Then delete by IDs (Pinecone doesn't support metadata-based delete directly)
    results = index.query(
        vector=[0.0] * get_settings().embedding_dimensions,
        top_k=10000,
        namespace=assessment_id,
        filter={"document_id": {"$eq": document_id}},
        include_metadata=False,
    )
    ids = [m["id"] for m in results.get("matches", [])]
    if ids:
        index.delete(ids=ids, namespace=assessment_id)
    logger.info(f"Deleted {len(ids)} vectors for document={document_id}")
