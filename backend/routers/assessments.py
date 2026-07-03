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
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import get_current_user
from config import get_settings
from models.schemas import (
    AssessmentRunRequest,
    AssessmentResponse,
    ControlOverrideRequest,
    RiskProfileRequest,
    ControlResult,
)
from models.controls import (
    calculate_scores,
    effective_score,
    resolve_framework_id,
    SCORE_MAP,
)
from services.aggregation import (
    build_gaps_summary,
    compute_inherent_risk,
    compute_residual_risk,
)
from services.followup import generate_follow_up_questions
from chains.assessment_graph import run_assessment
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

# ── In-process SSE progress state ────────────────────────────────────────────
# Simple in-memory dict keyed by assessment_id.  Sufficient for single-process
# deployments; replace with Redis pub/sub if horizontal scaling is needed.
_progress: dict[str, dict] = {}


def set_progress(assessment_id: str, step: str, message: str, percent: int) -> None:
    _progress[assessment_id] = {"step": step, "message": message, "percent": percent}


def clear_progress(assessment_id: str) -> None:
    _progress.pop(assessment_id, None)


async def stream_progress(assessment_id: str):
    """Async generator yielding SSE text events until the assessment completes.

    Polls every 0.5 s, yields only on state change, and terminates when
    step is 'complete' or 'error', percent >= 100, or after 10 min idle.
    """
    last_sent: dict | None = None
    idle_ticks = 0
    max_idle_ticks = 1200  # 600 s ÷ 0.5 s per tick

    while idle_ticks < max_idle_ticks:
        current = _progress.get(
            assessment_id, {"step": "idle", "message": "", "percent": 0}
        )
        if current != last_sent:
            last_sent = dict(current)
            idle_ticks = 0
            yield f"data: {json.dumps(current)}\n\n"
            if current.get("percent", 0) >= 100 or current.get("step") in (
                "complete",
                "error",
            ):
                break
        else:
            idle_ticks += 1
        await asyncio.sleep(0.5)


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
    framework_id: str = ""      # empty = reuse the framework of the previous run


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


def _enrich_record(record: dict) -> dict:
    """Attach computed (never stored) analysis fields to an assessment record.

    - needs_review per control: low-confidence AI scores with no override yet
    - review_queue: the control_ids awaiting human review
    - evidence_freshness: uploaded documents older than the staleness window
    - inherent_risk / residual_risk: derived from the stored risk_profile
    """
    settings = get_settings()

    # Human-review flags
    threshold = settings.review_confidence_threshold
    queue: list[str] = []
    for c in record.get("control_results", []):
        needs = (
            float(c.get("confidence", 1.0)) < threshold
            and not c.get("analyst_score")
        )
        c["needs_review"] = needs
        if needs:
            queue.append(c.get("control_id", ""))
    record["review_queue"] = queue

    # Evidence freshness
    stale_days = settings.evidence_stale_days
    now = datetime.now(timezone.utc)
    freshness = []
    for doc in list_documents(assessment_id=record["id"]):
        uploaded_raw = doc.get("created_at", "")
        age_days = None
        try:
            uploaded = datetime.fromisoformat(uploaded_raw)
            if uploaded.tzinfo is None:
                uploaded = uploaded.replace(tzinfo=timezone.utc)
            age_days = (now - uploaded).days
        except (ValueError, TypeError):
            pass
        freshness.append({
            "document_id": doc.get("id", ""),
            "file_name": doc.get("file_name", ""),
            "uploaded_at": uploaded_raw,
            "age_days": age_days,
            "stale": age_days is not None and age_days > stale_days,
        })
    record["evidence_freshness"] = {
        "threshold_days": stale_days,
        "documents": freshness,
        "stale_count": sum(1 for d in freshness if d["stale"]),
    }

    # Inherent & residual risk
    profile = record.get("risk_profile")
    if profile:
        inherent = compute_inherent_risk(profile)
        record["inherent_risk"] = inherent
        assessed = record.get("risk_level")
        if assessed:
            record["residual_risk"] = compute_residual_risk(
                inherent["tier"], str(assessed)
            )
    return record


@router.get("/{assessment_id}")
async def get_assessment_detail(assessment_id: str, user_id: str = Depends(get_current_user)):
    """Get a single assessment by ID, enriched with computed review,
    evidence-freshness, and inherent/residual risk fields."""
    record = get_assessment(assessment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return _enrich_record(record)


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
        framework_id = resolve_framework_id(req.framework_id)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        result = await run_assessment(
            vendor_name=req.vendor_name,
            assessment_id=req.assessment_id,
            framework_id=framework_id,
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
    existing = get_assessment(assessment_id)

    vendor_name = req.vendor_name
    if not vendor_name:
        if existing and existing.get("vendor_name"):
            vendor_name = existing["vendor_name"]
        else:
            raise HTTPException(
                status_code=400,
                detail="vendor_name is required (no existing assessment found)",
            )

    # Reuse the previous run's framework unless the request overrides it
    requested_framework = req.framework_id or (
        existing.get("framework_id", "") if existing else ""
    )
    try:
        framework_id = resolve_framework_id(requested_framework)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        result = await run_assessment(
            vendor_name=vendor_name,
            assessment_id=assessment_id,
            framework_id=framework_id,
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


# ── Human-in-the-loop: analyst score overrides ──────────────────────────────


@router.patch("/{assessment_id}/controls/{control_id}/override")
async def override_control_score(
    assessment_id: str,
    control_id: str,
    req: ControlOverrideRequest,
    user_id: str = Depends(get_current_user),
):
    """Set or clear an analyst override on one control's AI score.

    The original AI score is never modified — it stays in `score` as the
    audit trail.  All aggregate numbers (overall score, domain scores,
    risk level, gaps summary) are recomputed from the effective scores.
    Send score = null to clear an existing override.
    """
    record = get_assessment(assessment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Assessment not found")

    control_results = record.get("control_results", [])
    target = next(
        (c for c in control_results if c.get("control_id") == control_id), None
    )
    if target is None:
        raise HTTPException(
            status_code=404,
            detail=f"Control {control_id} not found in this assessment",
        )

    if req.score is None:
        target["analyst_score"] = None
        target["analyst_comment"] = None
        target["overridden_by"] = None
        target["overridden_at"] = None
    else:
        target["analyst_score"] = req.score.value
        target["analyst_comment"] = req.comment
        target["overridden_by"] = user_id
        target["overridden_at"] = datetime.now(timezone.utc).isoformat()

    # Recompute aggregates from effective (override-aware) scores.
    # Fall back to the default framework if this assessment ran against a
    # custom framework that has since been deleted.
    try:
        framework_id = resolve_framework_id(record.get("framework_id", ""))
    except KeyError:
        framework_id = resolve_framework_id("")
    scores = calculate_scores(control_results, framework_id)
    result_models = [ControlResult(**c) for c in control_results]
    gaps_summary = build_gaps_summary(result_models)

    update_assessment(assessment_id, {
        "control_results": control_results,
        "overall_score": scores["overall_score"],
        "risk_level": scores["risk_level"],
        "domain_scores": scores["domain_scores"],
        "gaps_summary": gaps_summary,
    })

    logger.info(
        f"Override on {assessment_id}/{control_id}: "
        f"{'cleared' if req.score is None else req.score.value} by '{user_id}'"
    )
    return {
        "success": True,
        "control": target,
        "overall_score": scores["overall_score"],
        "risk_level": scores["risk_level"],
        "domain_scores": scores["domain_scores"],
    }


# ── Re-assessment diff ───────────────────────────────────────────────────────


@router.get("/{assessment_id}/diff/{other_id}")
async def diff_assessments(
    assessment_id: str,
    other_id: str,
    user_id: str = Depends(get_current_user),
):
    """Compare two assessment runs control-by-control.

    `assessment_id` is the baseline (usually the older run) and
    `other_id` the comparison (usually the newer).  Uses effective
    (override-aware) scores.  Typically used to show how a vendor's
    posture changed after uploading updated documents.
    """
    base = get_assessment(assessment_id)
    compare = get_assessment(other_id)
    if not base or not compare:
        missing = assessment_id if not base else other_id
        raise HTTPException(status_code=404, detail=f"Assessment {missing} not found")

    base_by_id = {c["control_id"]: c for c in base.get("control_results", [])}
    comp_by_id = {c["control_id"]: c for c in compare.get("control_results", [])}

    controls_diff = []
    improved = regressed = changed = 0
    for cid in sorted(set(base_by_id) | set(comp_by_id)):
        b, c = base_by_id.get(cid), comp_by_id.get(cid)
        entry = {
            "control_id": cid,
            "title": (c or b).get("title", ""),
            "domain": (c or b).get("domain", ""),
            "base_score": effective_score(b) if b else None,
            "compare_score": effective_score(c) if c else None,
        }
        if b is None or c is None:
            entry["direction"] = "added" if b is None else "removed"
            changed += 1
        else:
            b_val = SCORE_MAP.get(entry["base_score"], 0.0)
            c_val = SCORE_MAP.get(entry["compare_score"], 0.0)
            if c_val > b_val:
                entry["direction"] = "improved"
                improved += 1
            elif c_val < b_val:
                entry["direction"] = "regressed"
                regressed += 1
            elif entry["base_score"] != entry["compare_score"]:
                entry["direction"] = "changed"   # e.g. FAIL → NO_EVIDENCE
                changed += 1
            else:
                entry["direction"] = "unchanged"
        controls_diff.append(entry)

    return {
        "base": {
            "id": base["id"],
            "created_at": base.get("created_at", ""),
            "overall_score": base.get("overall_score", 0),
            "risk_level": base.get("risk_level", ""),
            "framework_id": base.get("framework_id", "nist-800-53"),
        },
        "compare": {
            "id": compare["id"],
            "created_at": compare.get("created_at", ""),
            "overall_score": compare.get("overall_score", 0),
            "risk_level": compare.get("risk_level", ""),
            "framework_id": compare.get("framework_id", "nist-800-53"),
        },
        "framework_mismatch": (
            base.get("framework_id", "nist-800-53")
            != compare.get("framework_id", "nist-800-53")
        ),
        "score_delta": (
            (compare.get("overall_score", 0) or 0) - (base.get("overall_score", 0) or 0)
        ),
        "summary": {
            "improved": improved,
            "regressed": regressed,
            "changed": changed,
            "unchanged": sum(
                1 for e in controls_diff if e["direction"] == "unchanged"
            ),
        },
        "controls": controls_diff,
    }


# ── Inherent risk profile ────────────────────────────────────────────────────


@router.put("/{assessment_id}/risk-profile")
async def set_risk_profile(
    assessment_id: str,
    req: RiskProfileRequest,
    user_id: str = Depends(get_current_user),
):
    """Save the vendor relationship's inherent-risk intake profile.

    Stores the profile and returns the computed inherent tier — and,
    when the assessment has already been scored, the residual risk that
    combines both.
    """
    record = get_assessment(assessment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Assessment not found")

    profile = req.model_dump()
    inherent = compute_inherent_risk(profile)
    update_assessment(assessment_id, {"risk_profile": profile})

    response = {"success": True, "risk_profile": profile, "inherent_risk": inherent}
    assessed = record.get("risk_level")
    if assessed:
        response["residual_risk"] = compute_residual_risk(
            inherent["tier"], str(assessed)
        )
    return response


# ── Vendor follow-up questions ───────────────────────────────────────────────


@router.post("/{assessment_id}/follow-up-questions")
async def create_follow_up_questions(
    assessment_id: str,
    user_id: str = Depends(get_current_user),
):
    """Generate vendor-facing follow-up questions for every gapped control.

    Uses the LLM to draft one specific, answerable question per control
    whose effective score is not PASS.  The result is persisted on the
    assessment so it can be re-fetched without regenerating.
    """
    record = get_assessment(assessment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if record.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail="Run the assessment before generating follow-up questions",
        )

    try:
        questions = await asyncio.to_thread(generate_follow_up_questions, record)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    payload = {
        "questions": questions,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    update_assessment(assessment_id, {"follow_up_questions": payload})
    return payload


@router.get("/{assessment_id}/follow-up-questions")
async def get_follow_up_questions(
    assessment_id: str,
    user_id: str = Depends(get_current_user),
):
    """Return previously generated follow-up questions (404 if none yet)."""
    record = get_assessment(assessment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Assessment not found")
    saved = record.get("follow_up_questions")
    if not saved:
        raise HTTPException(
            status_code=404,
            detail="No follow-up questions generated yet — POST to this endpoint first",
        )
    return saved


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
