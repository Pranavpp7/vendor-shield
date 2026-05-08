"""Layer 6: Assessments Router — run, list, get, update, delete assessments.

RESPONSIBILITY:
    HTTP endpoints for managing vendor risk assessments.  The /run
    endpoint triggers the full LangGraph workflow (Layer 5).  All
    other endpoints delegate to local JSON storage and Qdrant.

IMPORTS FROM: chains/assessment_graph, storage/local_store,
              storage/qdrant_store, services/progress, models/schemas
IMPORTED BY:  main.py
"""

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import get_current_user
from models.schemas import AssessmentRunRequest, AssessmentResponse
from chains.assessment_graph import run_assessment
from services.progress import stream_progress, set_progress, clear_progress
from storage.local_store import (
    list_assessments,
    get_assessment,
    delete_assessment,
    update_assessment,
    list_documents,
    delete_document_meta,
    get_assessments_by_vendor,
)
from storage.qdrant_store import delete_collection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assessments", tags=["Assessments"])

# Endpoint-level guard — applied to every route except the SSE progress stream,
# which must stay public so EventSource cannot send custom headers.
_PROTECTED = [Depends(get_current_user)]

# Strong references to background tasks so the asyncio loop doesn't GC them
# while they're still pending. asyncio.create_task() only holds a weak ref.
_BACKGROUND_TASKS: set[asyncio.Task] = set()


def _spawn_background(coro) -> None:
    """Schedule a fire-and-forget coroutine without losing the reference."""
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)


# ── Request models ───────────────────────────────────────────────────────────


class RerunRequest(BaseModel):
    vendor_name: str = ""


class AssessmentUpdateRequest(BaseModel):
    notes: str | None = None
    chat_history: list | None = None


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("")
async def list_all_assessments(user_id: str = Depends(get_current_user)):
    """List assessments belonging to the current user, sorted newest first."""
    assessments = list_assessments(user_id=user_id)
    return {"assessments": assessments}


@router.get("/compare")
async def compare_assessments(ids: str, user_id: str = Depends(get_current_user)):
    """Return two full assessments side-by-side for the comparison page.

    The `ids` query parameter is a comma-separated pair of assessment IDs,
    e.g. ?ids=abc,def.  Both assessments are returned in the order requested
    so the frontend can label them as "left" and "right" deterministically.

    Note: declared BEFORE /{assessment_id} so FastAPI doesn't try to match
    "compare" as a path-parameter value.
    """
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    if len(id_list) != 2:
        raise HTTPException(
            status_code=400,
            detail="Exactly 2 assessment IDs required (e.g. ?ids=abc,def)",
        )

    assessments_out: list[dict] = []
    for aid in id_list:
        record = get_assessment(aid)
        if not record:
            raise HTTPException(status_code=404, detail=f"Assessment {aid} not found")
        assessments_out.append(record)

    return {"assessments": assessments_out}


@router.get("/{assessment_id}/progress")
async def assessment_progress(assessment_id: str):
    """SSE stream of assessment run progress (stage, message, percent).

    Connect before or immediately after calling /run.  The stream closes
    automatically when percent reaches 100 or after a 5-minute timeout.
    """
    return StreamingResponse(
        stream_progress(assessment_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{assessment_id}/run-history")
async def get_run_history(assessment_id: str, user_id: str = Depends(get_current_user)):
    """Return the list of previous runs for this assessment."""
    record = get_assessment(assessment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return {"run_history": record.get("run_history", [])}


@router.get("/{assessment_id}")
async def get_assessment_detail(assessment_id: str, user_id: str = Depends(get_current_user)):
    """Get a single assessment by ID."""
    record = get_assessment(assessment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return record


@router.post("/run", response_model=AssessmentResponse)
async def run_assessment_endpoint(req: AssessmentRunRequest, user_id: str = Depends(get_current_user)):
    """Run a full vendor risk assessment using the LangGraph workflow.

    Pipeline: ingest → retrieve → evaluate → aggregate → save
    Evaluates all 20 NIST controls concurrently against the vendor's
    uploaded documents using RAG + OpenRouter Llama 3.3 70B.

    Connect to GET /{assessment_id}/progress before calling this endpoint
    to receive live stage/percent updates via SSE.
    """
    try:
        result = await run_assessment(
            vendor_name=req.vendor_name,
            assessment_id=req.assessment_id,
        )
        # The LangGraph agent saves the assessment without user_id.
        # Stamp it immediately so list_assessments() filters correctly.
        if user_id:
            update_assessment(req.assessment_id, {"user_id": user_id})
        set_progress(req.assessment_id, "complete", "Assessment complete", 100)
        async def _delayed_clear(aid: str) -> None:
            await asyncio.sleep(2)
            clear_progress(aid)
        _spawn_background(_delayed_clear(req.assessment_id))
        return result
    except Exception as e:
        logger.error(f"Assessment run failed: {e}", exc_info=True)
        set_progress(req.assessment_id, "error", str(e), 0)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{assessment_id}/rerun", response_model=AssessmentResponse)
async def rerun_assessment(assessment_id: str, req: RerunRequest, user_id: str = Depends(get_current_user)):
    """Re-run an assessment with the latest document data.

    Useful after uploading additional documents to get updated scores.
    vendor_name is read from the existing record if not provided in body.
    """
    vendor_name = req.vendor_name
    if not vendor_name:
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
        if user_id:
            update_assessment(assessment_id, {"user_id": user_id})
        set_progress(assessment_id, "complete", "Assessment complete", 100)
        async def _delayed_clear(aid: str) -> None:
            await asyncio.sleep(2)
            clear_progress(aid)
        _spawn_background(_delayed_clear(assessment_id))
        return result
    except Exception as e:
        logger.error(f"Assessment rerun failed: {e}", exc_info=True)
        set_progress(assessment_id, "error", str(e), 0)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{assessment_id}")
async def update_assessment_partial(assessment_id: str, req: AssessmentUpdateRequest, user_id: str = Depends(get_current_user)):
    """Persist notes and/or chat history for an assessment.

    Only the fields provided in the request body are updated.
    """
    updates: dict = {}
    if req.notes is not None:
        updates["notes"] = req.notes
    if req.chat_history is not None:
        updates["chat_history"] = req.chat_history

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    result = update_assessment(assessment_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="Assessment not found")

    logger.info(f"Partial update for assessment {assessment_id}: {list(updates.keys())}")
    return {"success": True}


@router.delete("/{assessment_id}", dependencies=_PROTECTED)
async def delete_assessment_endpoint(assessment_id: str):
    """Delete an assessment and all associated data.

    Cascade:
    1. Delete all document metadata JSONs and raw upload files
    2. Delete the Qdrant vector collection
    3. Delete the assessment JSON
    """
    try:
        # 1. Delete document metadata and raw uploaded files
        docs = list_documents(assessment_id=assessment_id)
        for doc in docs:
            upload_path = doc.get("upload_path")
            if upload_path:
                try:
                    Path(upload_path).unlink(missing_ok=True)
                except Exception as e:
                    logger.warning(f"Upload file cleanup failed: {e}")
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


# ── Vendor router ────────────────────────────────────────────────────────────
# Same file, different prefix.  Mounted alongside `router` from main.py.

vendors_router = APIRouter(prefix="/api/vendors", tags=["Vendors"])


@vendors_router.get("/{vendor_name}/history")
async def vendor_history(vendor_name: str, user_id: str = Depends(get_current_user)):
    """Return every assessment recorded for this vendor, oldest first.

    Each entry carries only the fields the trend chart needs:
    id, score, domain_scores, created_at.  FastAPI auto-decodes the
    URL-encoded vendor_name path parameter, so an exact match against
    the stored vendor_name field is sufficient.
    """
    history = get_assessments_by_vendor(vendor_name, user_id=user_id)
    return {
        "vendor_name": vendor_name,
        "history": [
            {
                "id": h["id"],
                "score": h.get("overall_score", 0),
                "domain_scores": h.get("domain_scores", {}),
                "created_at": h.get("created_at", ""),
            }
            for h in history
        ],
    }
