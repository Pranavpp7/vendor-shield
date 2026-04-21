"""
Layer 3: Document Ingestion Pipeline.

RESPONSIBILITY:
    Orchestrates the full ingestion flow: extract → chunk → embed → store.
    This is the ONLY service that calls other services — it is the pipeline
    coordinator for getting documents into the system.

    No LLM calls, no assessment logic, no HTTP handling.

PIPELINE:
    1. Generate a document ID
    2. Save raw file to data/uploads/
    3. Extract text (PDF, DOCX, or URL)
    4. Split into overlapping chunks
    5. Embed chunks into 1024-dim vectors
    6. Store vectors in Qdrant (one collection per assessment)
    7. Save document metadata as JSON

IMPORTS FROM: services/extraction, services/chunking, services/embedding,
              storage/qdrant_store, storage/local_store, config
IMPORTED BY:  mcp/server.py, routers/documents.py
"""

import logging
from pathlib import Path

from config import get_settings
from services.extraction import extract_pdf, extract_text_file, extract_url
from services.chunking import split_text
from services.embedding import embed_chunks
from storage.qdrant_store import add_chunks
from storage.local_store import generate_id, save_document_meta
from models.schemas import DocumentUploadResponse

logger = logging.getLogger(__name__)


def _upload_dir() -> Path:
    """Resolve the upload directory as an absolute path."""
    settings = get_settings()
    base = Path(__file__).resolve().parent.parent  # backend/
    path = base / settings.upload_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


def ingest_file(
    file_bytes: bytes,
    filename: str,
    assessment_id: str,
    vendor_name: str,
) -> DocumentUploadResponse:
    """Run the full ingestion pipeline for an uploaded file.

    Args:
        file_bytes: Raw file content.
        filename: Original filename (determines extraction method).
        assessment_id: Which assessment this document belongs to.
        vendor_name: Vendor name for metadata.

    Returns:
        DocumentUploadResponse with document_id, chunk count, and status.
    """
    document_id = generate_id()
    logger.info(
        f"Ingesting file '{filename}' for assessment {assessment_id} "
        f"(doc_id={document_id})"
    )

    # 1. Save raw file to uploads folder
    upload_path = _upload_dir() / f"{document_id}_{filename}"
    upload_path.write_bytes(file_bytes)
    logger.info(f"Saved upload to {upload_path}")

    # 2. Extract text based on file type
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext == "pdf":
        pages = extract_pdf(file_bytes, filename)
    else:
        pages = extract_text_file(file_bytes, filename)

    if not pages:
        logger.warning(f"No text extracted from '{filename}'")
        save_document_meta(document_id, {
            "assessment_id": assessment_id,
            "vendor_name": vendor_name,
            "file_name": filename,
            "file_size": len(file_bytes),
            "source_type": "file",
            "status": "empty",
            "chunks_created": 0,
        })
        return DocumentUploadResponse(
            document_id=document_id,
            chunks_created=0,
            embeddings_generated=False,
            status="empty",
            file_name=filename,
            file_size=len(file_bytes),
        )

    # 3. Flatten pages into a single text string
    full_text = "\n\n".join(page.text for page in pages)

    # 4. Chunk the text
    chunks = split_text(full_text)
    logger.info(f"Created {len(chunks)} chunks from '{filename}'")

    # 5. Embed the chunks
    vectors = embed_chunks(chunks)
    logger.info(f"Generated {len(vectors)} embeddings")

    # 6. Store vectors in Qdrant
    vector_count = add_chunks(assessment_id, chunks, vectors, filename)

    # 7. Save document metadata as JSON
    save_document_meta(document_id, {
        "assessment_id": assessment_id,
        "vendor_name": vendor_name,
        "file_name": filename,
        "file_size": len(file_bytes),
        "source_type": "file",
        "status": "processed",
        "chunks_created": len(chunks),
    })

    logger.info(
        f"Ingestion complete: '{filename}' → {len(chunks)} chunks, "
        f"{vector_count} vectors stored"
    )
    return DocumentUploadResponse(
        document_id=document_id,
        chunks_created=len(chunks),
        embeddings_generated=True,
        status="processed",
        file_name=filename,
        file_size=len(file_bytes),
    )


def ingest_url(
    url: str,
    assessment_id: str,
    vendor_name: str,
) -> DocumentUploadResponse:
    """Run the full ingestion pipeline for a URL.

    Args:
        url: The URL to fetch and ingest.
        assessment_id: Which assessment this document belongs to.
        vendor_name: Vendor name for metadata.

    Returns:
        DocumentUploadResponse with document_id, chunk count, and status.
    """
    document_id = generate_id()
    logger.info(
        f"Ingesting URL '{url}' for assessment {assessment_id} "
        f"(doc_id={document_id})"
    )

    # 1. Fetch and extract text from URL
    pages = extract_url(url)
    source_name = pages[0].source if pages else url

    # 2. Flatten into a single text string
    full_text = "\n\n".join(page.text for page in pages)

    # 3. Chunk the text
    chunks = split_text(full_text)
    logger.info(f"Created {len(chunks)} chunks from URL")

    # 4. Embed the chunks
    vectors = embed_chunks(chunks)

    # 5. Store vectors in Qdrant
    vector_count = add_chunks(assessment_id, chunks, vectors, source_name)

    # 6. Save document metadata as JSON
    save_document_meta(document_id, {
        "assessment_id": assessment_id,
        "vendor_name": vendor_name,
        "file_name": source_name,
        "source_url": url,
        "source_type": "url",
        "status": "processed",
        "chunks_created": len(chunks),
    })

    logger.info(
        f"Ingestion complete: URL → {len(chunks)} chunks, "
        f"{vector_count} vectors stored"
    )
    return DocumentUploadResponse(
        document_id=document_id,
        chunks_created=len(chunks),
        embeddings_generated=True,
        status="processed",
        source_url=url,
    )
