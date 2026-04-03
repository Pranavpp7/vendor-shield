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
        raise HTTPException(status_code=400, detail="vendor_name is required")

    try:
        result = await run_assessment(
            vendor_name=vendor_name,
            assessment_id=assessment_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
