"""Chat and summary generation endpoints."""

from fastapi import APIRouter, HTTPException
from models.schemas import ChatRequest, ChatResponse, SummaryRequest, SummaryResponse
from services.chat import chat_with_docs, generate_summary

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """Chat over vendor documents with RAG context.

    Retrieves relevant chunks from Pinecone, enriches the prompt,
    and responds using Groq Llama.
    """
    try:
        reply, sources = await chat_with_docs(
            question=req.question,
            assessment_id=req.assessment_id,
            context=req.context,
        )
        return ChatResponse(reply=reply, sources=sources)
    except Exception as e:
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
        raise HTTPException(status_code=500, detail=str(e))
