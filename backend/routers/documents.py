"""Document upload and ingestion endpoints."""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from models.schemas import DocumentUploadResponse, URLIngestRequest
from services.ingestion import ingest_file, ingest_url

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    assessment_id: str = Form(...),
    vendor_name: str = Form(...),
    user_id: str = Form(None),
):
    """Upload a PDF/DOCX/text file → extract → chunk → embed → store in Pinecone."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    file_bytes = await file.read()
    content_type = file.content_type or "application/octet-stream"

    try:
        result = await ingest_file(
            file_bytes=file_bytes,
            filename=file.filename,
            content_type=content_type,
            assessment_id=assessment_id,
            vendor_name=vendor_name,
            user_id=user_id,
        )
        return DocumentUploadResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest-url", response_model=DocumentUploadResponse)
async def ingest_url_endpoint(req: URLIngestRequest):
    """Ingest URL content → chunk → embed → store in Pinecone."""
    try:
        result = await ingest_url(
            url=req.url,
            assessment_id=req.assessment_id,
            vendor_name=req.vendor_name,
        )
        return DocumentUploadResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{assessment_id}")
async def list_documents(assessment_id: str):
    """List all documents for an assessment."""
    from supabase import create_client
    from config import get_settings

    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)
    result = (
        supabase.table("documents")
        .select("id, file_name, file_size, content_type, status, created_at, source_url")
        .eq("assessment_id", assessment_id)
        .order("created_at", desc=True)
        .execute()
    )
    return {"documents": result.data}


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and its vectors from Pinecone."""
    from supabase import create_client
    from config import get_settings
    from services.pinecone_store import delete_by_document

    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)

    # Get document to find assessment_id
    doc = supabase.table("documents").select("assessment_id").eq("id", document_id).single().execute()
    if not doc.data:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete vectors from Pinecone
    delete_by_document(doc.data["assessment_id"], document_id)

    # Delete from Supabase
    supabase.table("documents").delete().eq("id", document_id).execute()

    return {"success": True, "message": f"Document {document_id} deleted"}
