"""Assessment run and report endpoints."""

from fastapi import APIRouter, HTTPException
from models.schemas import AssessmentRunRequest, AssessmentResponse
from chains.assessment_graph import run_assessment

router = APIRouter(prefix="/api/assessments", tags=["Assessments"])


@router.post("/run", response_model=AssessmentResponse)
async def run_assessment_endpoint(req: AssessmentRunRequest):
    """Run a full vendor risk assessment using the LangGraph workflow.

    Retrieves evidence from Pinecone, evaluates each control via Groq Llama,
    computes scores, and generates an executive summary.
    """
    try:
        result = await run_assessment(
            vendor_name=req.vendor_name,
            assessment_id=req.assessment_id,
            controls=req.controls,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{assessment_id}/rerun", response_model=AssessmentResponse)
async def rerun_assessment(assessment_id: str, vendor_name: str = ""):
    """Re-run assessment with latest document data."""
    if not vendor_name:
        # Try to get vendor name from Supabase
        from supabase import create_client
        from config import get_settings
        settings = get_settings()
        supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)
        result = supabase.table("assessments").select("vendor_name").eq("id", assessment_id).single().execute()
        if result.data:
            vendor_name = result.data["vendor_name"]
        else:
            raise HTTPException(status_code=404, detail="Assessment not found")

    try:
        result = await run_assessment(
            vendor_name=vendor_name,
            assessment_id=assessment_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{assessment_id}/report")
async def get_assessment_report(assessment_id: str):
    """Get the latest assessment report from Supabase."""
    from supabase import create_client
    from config import get_settings

    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)
    result = supabase.table("assessments").select("*").eq("id", assessment_id).single().execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Assessment not found")

    return result.data
