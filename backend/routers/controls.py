"""Layer 6: Controls Router — exposes control frameworks and their checklists.

RESPONSIBILITY:
    Read-only endpoints that return the available assessment frameworks,
    their security control definitions, and domain lists.  No state
    mutations, no service calls.

IMPORTS FROM: models/controls, models/schemas
IMPORTED BY:  main.py
"""

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user
from models.schemas import ControlsListResponse
from models.controls import get_all_controls, get_domains, list_frameworks

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
