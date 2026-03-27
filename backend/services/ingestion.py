"""Document ingestion orchestrator — extract, chunk, embed, store."""

import uuid
import logging
from supabase import create_client
from config import get_settings
from services.extraction import extract_pdf, extract_text_file, extract_url
from services.chunking import split_into_chunks
from services.pinecone_store import upsert_chunks

logger = logging.getLogger(__name__)


def _get_supabase():
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


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
    supabase = _get_supabase()
    document_id = str(uuid.uuid4())

    # Create document record in Supabase
    supabase.table("documents").insert({
        "id": document_id,
        "assessment_id": assessment_id,
        "file_name": filename,
        "file_size": len(file_bytes),
        "content_type": content_type,
        "storage_path": storage_path or "",
        "status": "processing",
        "user_id": user_id,
    }).execute()

    try:
        # Extract text
        if "pdf" in content_type.lower():
            pages = extract_pdf(file_bytes, filename)
        else:
            pages = extract_text_file(file_bytes, filename)

        if not pages:
            supabase.table("documents").update({"status": "error"}).eq("id", document_id).execute()
            raise ValueError(f"Could not extract text from {filename}")

        # Chunk
        settings = get_settings()
        chunks = split_into_chunks(pages, settings.chunk_size, settings.chunk_overlap)

        # Embed and store in Pinecone
        count = upsert_chunks(assessment_id, vendor_name, filename, chunks, document_id)

        # Update status
        supabase.table("documents").update({"status": "ready"}).eq("id", document_id).execute()

        logger.info(f"Ingested {filename}: {len(pages)} pages, {len(chunks)} chunks, {count} vectors")
        return {
            "document_id": document_id,
            "chunks_created": len(chunks),
            "embeddings_generated": True,
            "status": "ready",
        }

    except Exception as e:
        supabase.table("documents").update({"status": "error"}).eq("id", document_id).execute()
        logger.error(f"Ingestion failed for {filename}: {e}")
        raise


async def ingest_url(
    url: str,
    assessment_id: str,
    vendor_name: str,
    user_id: str | None = None,
) -> dict:
    """Fetch URL content → chunk → embed → store in Pinecone."""
    # Extract text from URL
    pages = await extract_url(url)

    if not pages:
        raise ValueError(f"Could not extract text from {url}")

    display_name = pages[0].source
    document_id = str(uuid.uuid4())
    supabase = _get_supabase()

    # Create document record
    supabase.table("documents").insert({
        "id": document_id,
        "assessment_id": assessment_id,
        "file_name": display_name,
        "file_size": sum(len(p.text) for p in pages),
        "content_type": "text/html",
        "source_type": "url",
        "source_url": url,
        "status": "processing",
        "user_id": user_id,
    }).execute()

    try:
        settings = get_settings()
        chunks = split_into_chunks(pages, settings.chunk_size, settings.chunk_overlap)
        count = upsert_chunks(assessment_id, vendor_name, display_name, chunks, document_id)

        supabase.table("documents").update({"status": "ready"}).eq("id", document_id).execute()

        logger.info(f"Ingested URL {url}: {len(chunks)} chunks, {count} vectors")
        return {
            "document_id": document_id,
            "chunks_created": len(chunks),
            "embeddings_generated": True,
            "status": "ready",
        }

    except Exception as e:
        supabase.table("documents").update({"status": "error"}).eq("id", document_id).execute()
        raise
