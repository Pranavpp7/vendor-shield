"""Layer 6: Chat Router — RAG chat, summary generation, chat history.

RESPONSIBILITY:
    HTTP endpoints for chatting over vendor documents and generating
    executive summaries.  Persists chat history to local JSON storage.

IMPORTS FROM: services/chat, storage/local_store, models/schemas
IMPORTED BY:  main.py
"""

import logging
from fastapi import APIRouter, HTTPException, Depends

from auth import get_current_user
from models.schemas import ChatRequest, ChatResponse, SummaryRequest, SummaryResponse
from services.chat import chat_with_docs, generate_summary
from storage.local_store import save_chat_message, get_chat_history

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/chat",
    tags=["Chat"],
    dependencies=[Depends(get_current_user)],
)


@router.post("", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """Chat over vendor documents with RAG context.

    Retrieves relevant chunks from Qdrant, enriches the prompt,
    and responds using OpenRouter Llama 3.3 70B.  Saves the Q&A pair
    to local chat history.
    """
    try:
        reply, sources = await chat_with_docs(
            question=req.question,
            assessment_id=req.assessment_id,
            context=req.context,
        )

        # Persist chat history (citations saved with assistant message)
        save_chat_message(req.assessment_id, "user", req.question)
        save_chat_message(
            req.assessment_id, "assistant", reply,
            [s.model_dump() for s in sources],
        )

        return ChatResponse(reply=reply, sources=sources)
    except Exception as e:
        logger.error(f"Chat failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summary", response_model=SummaryResponse)
async def summary_endpoint(req: SummaryRequest):
    """Generate an executive summary for a vendor assessment."""
    try:
        summary = await generate_summary(
            vendor_name=req.vendor_name,
            score=req.score,
            risk_level=req.risk_level,
            controls=req.controls,
            notes=req.notes,
        )
        return SummaryResponse(summary=summary)
    except Exception as e:
        logger.error(f"Summary generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{assessment_id}/history")
async def chat_history_endpoint(assessment_id: str):
    """Get the full chat history for an assessment."""
    history = get_chat_history(assessment_id)
    return {"assessment_id": assessment_id, "messages": history}
