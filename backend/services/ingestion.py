"""Document ingestion orchestrator — extract, chunk, embed, store."""

import uuid
import logging
from config import get_settings
from services.extraction import extract_pdf, extract_text_file, extract_url
from services.chunking import split_into_chunks
from services.pinecone_store import upsert_chunks

logger = logging.getLogger(__name__)


async def ingest_file(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    assessment_id: str,
    vendor_name: str,
    storage_path: str | None = None,
    user_id: str | None = None,
) -> dict:
    """Full pipeline: extract text → chunk → embed → store in Pinecone."""
    document_id = str(uuid.uuid4())

    # Extract text
    if "pdf" in content_type.lower():
        pages = extract_pdf(file_bytes, filename)
    else:
        pages = extract_text_file(file_bytes, filename)

    if not pages:
        raise ValueError(f"Could not extract text from {filename}")

    # Chunk
    settings = get_settings()
    chunks = split_into_chunks(pages, settings.chunk_size, settings.chunk_overlap)

    # Embed and store in Pinecone
    count = upsert_chunks(assessment_id, vendor_name, filename, chunks, document_id)

    logger.info(f"Ingested {filename}: {len(pages)} pages, {len(chunks)} chunks, {count} vectors")
    return {
        "document_id": document_id,
        "file_name": filename,
        "file_size": len(file_bytes),
        "chunks_created": len(chunks),
        "embeddings_generated": True,
        "status": "ready",
    }


async def ingest_url(
    url: str,
    assessment_id: str,
    vendor_name: str,
    user_id: str | None = None,
) -> dict:
    """Fetch URL content → chunk → embed → store in Pinecone."""
    pages = await extract_url(url)

    if not pages:
        raise ValueError(f"Could not extract text from {url}")

    display_name = pages[0].source
    document_id = str(uuid.uuid4())

    settings = get_settings()
    chunks = split_into_chunks(pages, settings.chunk_size, settings.chunk_overlap)
    count = upsert_chunks(assessment_id, vendor_name, display_name, chunks, document_id)

    logger.info(f"Ingested URL {url}: {len(chunks)} chunks, {count} vectors")
    return {
        "document_id": document_id,
        "file_name": display_name,
        "file_size": sum(len(p.text) for p in pages),
        "source_url": url,
        "chunks_created": len(chunks),
        "embeddings_generated": True,
        "status": "ready",
    }
