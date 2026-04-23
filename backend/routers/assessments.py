"""Layer 6: Assessments Router — run, list, get, delete assessments.

RESPONSIBILITY:
    HTTP endpoints for managing vendor risk assessments.  The /run
    endpoint triggers the full LangGraph workflow (Layer 5).  All
    other endpoints delegate to local JSON storage and Qdrant.

IMPORTS FROM: chains/assessment_graph, storage/local_store,
              storage/qdrant_store, models/schemas
IMPORTED BY:  main.py
"""

import logging
from fastapi import APIRouter, HTTPException

from models.schemas import AssessmentRunRequest, AssessmentResponse
from chains.assessment_graph import run_assessment
from storage.local_store import (
    list_assessments,
    get_assessment,
    delete_assessment,
    list_documents,
    delete_document_meta,
)
from storage.qdrant_store import delete_collection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assessments", tags=["Assessments"])


@router.get("")
async def list_all_assessments():
    """List all assessments, sorted newest first."""
    assessments = list_assessments()
    return {"assessments": assessments}


@router.get("/{assessment_id}")
async def get_assessment_detail(assessment_id: str):
    """Get a single assessment by ID."""
    record = get_assessment(assessment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return record


@router.post("/run", response_model=AssessmentResponse)
async def run_assessment_endpoint(req: AssessmentRunRequest):
    """Run a full vendor risk assessment using the LangGraph workflow.

    Pipeline: check_documents → evaluate_controls → aggregate → save_results
    Evaluates all 20 NIST controls concurrently against the vendor's
    uploaded documents using RAG + Groq Llama 3.3 70B.
    """
    try:
        result = await run_assessment(
            vendor_name=req.vendor_name,
            assessment_id=req.assessment_id,
        )
        return result
    except Exception as e:
        logger.error(f"Assessment run failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{assessment_id}/rerun", response_model=AssessmentResponse)
async def rerun_assessment(assessment_id: str, vendor_name: str = ""):
    """Re-run an assessment with the latest document data.

    Useful after uploading additional documents to get updated scores.
    """
    if not vendor_name:
        # Try to read vendor_name from the existing assessment
        existing = get_assessment(assessment_id)
        if existing and existing.get("vendor_name"):
            vendor_name = existing["vendor_name"]
        else:
            raise HTTPException(
                status_code=400,
                detail="vendor_name is required (no existing assessment found)",
            )

    try:
        result = await run_assessment(
            vendor_name=vendor_name,
            assessment_id=assessment_id,
        )
        return result
    except Exception as e:
        logger.error(f"Assessment rerun failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{assessment_id}")
async def delete_assessment_endpoint(assessment_id: str):
    """Delete an assessment and all associated data.

    Cascade:
    1. Delete all document metadata JSONs for this assessment
    2. Delete the Qdrant vector collection
    3. Delete the assessment JSON
    """
    try:
        # 1. Delete document metadata
        docs = list_documents(assessment_id=assessment_id)
        for doc in docs:
            delete_document_meta(doc["id"])
        logger.info(f"Deleted {len(docs)} document records for {assessment_id}")

        # 2. Delete Qdrant vectors
        try:
            delete_collection(assessment_id)
            logger.info(f"Deleted Qdrant collection for {assessment_id}")
        except Exception as e:
            logger.warning(f"Qdrant collection delete failed (may not exist): {e}")

        # 3. Delete assessment record
        deleted = delete_assessment(assessment_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Assessment not found")

        return {
            "success": True,
            "message": f"Assessment {assessment_id} and all associated data deleted",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Assessment delete failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
