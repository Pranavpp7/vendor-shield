"""Layer 6: Documents Router — file upload, URL ingestion, listing, deletion.

RESPONSIBILITY:
    HTTP endpoints for managing vendor documents.  Each handler validates
    input, delegates to services/storage, and returns the result.
    No business logic, no direct DB/vector operations.

IMPORTS FROM: services/ingestion, storage/local_store, storage/qdrant_store,
              models/schemas
IMPORTED BY:  main.py
"""

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends

from auth import get_current_user
from models.schemas import DocumentUploadResponse, URLIngestRequest
from services.ingestion import ingest_file, ingest_url
from storage.local_store import (
    list_documents,
    get_document_meta,
    delete_document_meta,
)
from storage.qdrant_store import delete_document_vectors

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/documents",
    tags=["Documents"],
    dependencies=[Depends(get_current_user)],
)

# Allowed file extensions
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
# 50 MB hard cap
MAX_FILE_BYTES = 50 * 1024 * 1024


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    assessment_id: str = Form(...),
    vendor_name: str = Form(...),
):
    """Upload a PDF/DOCX/text file → extract → chunk → embed → store.

    Validates file type, size, and duplicate name before running the
    ingestion pipeline in a thread so the event loop stays unblocked.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # 1. File type validation
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    file_bytes = await file.read()

    # 2. Empty file guard
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # 3. File size cap
    if len(file_bytes) > MAX_FILE_BYTES:
        mb = len(file_bytes) / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({mb:.1f} MB). Maximum allowed size is 50 MB.",
        )

    # 4. Duplicate filename detection within the same assessment
    existing_docs = list_documents(assessment_id=assessment_id)
    if any(d.get("file_name") == file.filename for d in existing_docs):
        raise HTTPException(
            status_code=409,
            detail=f"'{file.filename}' has already been uploaded to this assessment. Delete the existing file first if you want to replace it.",
        )

    # 5. Run synchronous ingestion pipeline in a thread (embedding is CPU-heavy)
    try:
        result = await asyncio.to_thread(
            ingest_file,
            file_bytes,
            file.filename,
            assessment_id,
            vendor_name,
        )
        return result
    except Exception as e:
        logger.error(f"Upload failed for '{file.filename}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest-url", response_model=DocumentUploadResponse)
async def ingest_url_endpoint(req: URLIngestRequest):
    """Ingest a URL's content → extract → chunk → embed → store.

    Runs the synchronous pipeline in a thread so the event loop is free.
    """
    try:
        result = await asyncio.to_thread(
            ingest_url,
            req.url,
            req.assessment_id,
            req.vendor_name,
        )
        return result
    except Exception as e:
        logger.error(f"URL ingestion failed for '{req.url}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{assessment_id}")
async def list_assessment_documents(assessment_id: str):
    """List all documents uploaded for a specific assessment."""
    docs = list_documents(assessment_id=assessment_id)
    return {"documents": docs}


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """Delete a document: removes Qdrant vectors, raw upload file, and metadata.

    Cascade:
    1. Delete all Qdrant vectors tagged with this document's filename
    2. Delete the raw uploaded file from data/uploads/
    3. Delete the document metadata JSON
    """
    doc = get_document_meta(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    assessment_id = doc.get("assessment_id")
    file_name = doc.get("file_name")

    # 1. Remove vectors from Qdrant (so they don't appear in future retrievals)
    if assessment_id and file_name:
        try:
            await asyncio.to_thread(delete_document_vectors, assessment_id, file_name)
        except Exception as e:
            logger.warning(f"Vector deletion failed for document {document_id}: {e}")

    # 2. Delete the raw uploaded file
    upload_path = doc.get("upload_path")
    if upload_path:
        try:
            Path(upload_path).unlink(missing_ok=True)
            logger.info(f"Deleted raw upload file: {upload_path}")
        except Exception as e:
            logger.warning(f"Upload file cleanup failed for {document_id}: {e}")

    # 3. Delete metadata JSON
    deleted = delete_document_meta(document_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete document metadata")

    logger.info(f"Deleted document {document_id} (file: {file_name})")
    return {"success": True, "message": f"Document {document_id} deleted"}
