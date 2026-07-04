"""Layer 6: Controls Router — control frameworks and their checklists.

RESPONSIBILITY:
    Endpoints for browsing frameworks/controls, extracting a DRAFT
    framework from an uploaded compliance document (LLM), and saving or
    deleting user-created frameworks.  Extraction never persists anything
    — a draft only becomes usable after the user reviews it and POSTs it
    back, where it is schema-validated.

IMPORTS FROM: models/controls, models/schemas,
              services/framework_extraction, services/extraction
IMPORTED BY:  main.py
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import ValidationError

from auth import get_current_user
from models.schemas import ControlsListResponse, FrameworkDefinition
from models.controls import (
    get_all_controls,
    get_domains,
    list_frameworks,
    save_custom_framework,
    delete_custom_framework,
)
from services.extraction import extract_pdf, extract_text_file
from services.framework_extraction import extract_framework_from_text

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/controls",
    tags=["Controls"],
    dependencies=[Depends(get_current_user)],
)

frameworks_router = APIRouter(
    prefix="/api/frameworks",
    tags=["Controls"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=ControlsListResponse)
async def list_controls(framework_id: str | None = None):
    """Get a framework's security controls and domain names.

    Defaults to the NIST SP 800-53 framework when framework_id is omitted.
    """
    try:
        controls = get_all_controls(framework_id)
        domains = get_domains(framework_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return ControlsListResponse(controls=controls, domains=domains)


@router.get("/domains")
async def list_domains(framework_id: str | None = None):
    """Get the list of control domain names for a framework."""
    try:
        return {"domains": get_domains(framework_id)}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@frameworks_router.get("")
async def get_frameworks():
    """List every available control framework with summary metadata."""
    return {"frameworks": list_frameworks()}


@frameworks_router.post("/extract")
async def extract_framework(file: UploadFile = File(...)):
    """Draft a control framework from an uploaded compliance document.

    Accepts PDF, DOCX, or plain text (a questionnaire, standard excerpt,
    or internal checklist).  Returns the DRAFT framework for review —
    nothing is saved until the user POSTs the reviewed version to
    POST /api/frameworks.
    """
    file_bytes = await file.read()
    filename = file.filename or "uploaded-document"

    if len(file_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Document too large (max 20 MB)")
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        if filename.lower().endswith(".pdf"):
            pages = extract_pdf(file_bytes, filename)
        else:
            pages = extract_text_file(file_bytes, filename)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not read document: {e}")

    text = "\n\n".join(p.text for p in pages)

    try:
        # LLM call is sync — keep the event loop free
        draft = await asyncio.to_thread(extract_framework_from_text, filename, text)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {"draft": draft}


@frameworks_router.post("")
async def save_framework(definition: FrameworkDefinition):
    """Save a reviewed framework as a custom framework.

    Validates the full schema (substantive text in every field), rejects
    duplicate control ids, and refuses to shadow built-in framework ids.
    Saving an existing custom id updates it.
    """
    ids = [c.id for c in definition.controls]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise HTTPException(
            status_code=422, detail=f"Duplicate control ids: {sorted(dupes)}"
        )

    payload = definition.model_dump(by_alias=True)
    try:
        saved = save_custom_framework(payload)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {
        "success": True,
        "framework": {
            "id": saved["id"],
            "name": saved.get("name", ""),
            "control_count": len(saved.get("controls", [])),
            "domains": sorted({c["domain"] for c in saved.get("controls", [])}),
        },
    }


@frameworks_router.delete("/{framework_id}")
async def remove_framework(framework_id: str):
    """Delete a custom framework.  Built-in frameworks cannot be deleted."""
    try:
        deleted = delete_custom_framework(framework_id)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Framework '{framework_id}' not found")
    return {"success": True}
