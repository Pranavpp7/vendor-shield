"""Layer 6: Controls Router — exposes the 20-control NIST checklist.

RESPONSIBILITY:
    Read-only endpoints that return the static security control
    definitions and domain list.  No state mutations, no service calls.

IMPORTS FROM: models/controls, models/schemas
IMPORTED BY:  main.py
"""

from fastapi import APIRouter, Depends

from auth import get_current_user
from models.schemas import ControlsListResponse
from models.controls import get_all_controls, get_domains

router = APIRouter(
    prefix="/api/controls",
    tags=["Controls"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=ControlsListResponse)
async def list_controls():
    """Get all 20 security controls and the 4 domain names."""
    controls = get_all_controls()
    domains = get_domains()
    return ControlsListResponse(controls=controls, domains=domains)


@router.get("/domains")
async def list_domains():
    """Get the list of control domain names."""
    return {"domains": get_domains()}
