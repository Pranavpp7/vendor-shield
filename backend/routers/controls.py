"""Controls repository endpoints."""

from fastapi import APIRouter
from models.schemas import ControlsListResponse, ControlDefinition
from models.controls import get_all_controls, get_categories

router = APIRouter(prefix="/api/controls", tags=["Controls"])


@router.get("", response_model=ControlsListResponse)
async def list_controls():
    """Get all internal controls (the policy checklist)."""
    controls = get_all_controls()
    categories = get_categories()
    return ControlsListResponse(controls=controls, categories=categories)


@router.get("/categories")
async def list_categories():
    """Get list of control category names."""
    return {"categories": get_categories()}
