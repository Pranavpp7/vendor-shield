"""
Layer 6: Email Router — send PDF risk reports via email.

RESPONSIBILITY:
    HTTP endpoint for generating and emailing a PDF risk assessment
    report to a specified recipient.  Delegates to services/email_service.

IMPORTS FROM: services/email_service, storage/local_store, models/schemas
IMPORTED BY:  main.py
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr

from auth import get_current_user
from services.email_service import send_report_email
from storage.local_store import get_assessment

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/email",
    tags=["Email"],
    dependencies=[Depends(get_current_user)],
)


class SendReportRequest(BaseModel):
    """Request body for the send-report endpoint."""
    assessment_id: str
    recipient_email: EmailStr


@router.post("/send-report")
async def send_report(req: SendReportRequest):
    """Generate a PDF risk report and email it to a recipient.

    Steps:
    1. Load the assessment from local JSON storage.
    2. Verify the assessment exists and is completed.
    3. Generate a PDF and send it via Resend.
    4. Return the Resend message ID on success.
    """
    # 1. Load assessment
    assessment = get_assessment(req.assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # 2. Check status
    if assessment.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Assessment is not completed (status: {assessment.get('status', 'unknown')})",
        )

    # 3. Send the report
    result = send_report_email(str(req.recipient_email), assessment)

    if not result.get("success"):
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Failed to send email"),
        )

    # 4. Return success
    logger.info(f"Report sent to {req.recipient_email} for assessment {req.assessment_id}")
    return {
        "message": f"Report sent successfully to {req.recipient_email}",
        "message_id": result.get("message_id", ""),
    }
