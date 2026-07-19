"""Layer 6: Chat Router — RAG chat, summary generation, chat history.

RESPONSIBILITY:
    HTTP endpoints for chatting over vendor documents and generating
    executive summaries.  Persists chat history to local JSON storage.

IMPORTS FROM: services/chat, storage/local_store, models/schemas
IMPORTED BY:  main.py
"""

import asyncio
import logging
from fastapi import APIRouter, HTTPException, Depends

from auth import get_current_user
from config import get_settings
from models.schemas import ChatRequest, ChatResponse, SummaryRequest, SummaryResponse
from services.chat import build_history_messages, chat_with_docs, generate_summary
from services.memory import recall, remember
from storage.local_store import save_chat_message, get_chat_history

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/chat",
    tags=["Chat"],
    dependencies=[Depends(get_current_user)],
)

# Fire-and-forget memory-extraction tasks: hold references so the event
# loop can't garbage-collect them mid-flight.
_bg_tasks: set[asyncio.Task] = set()


@router.post("", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, user_id: str = Depends(get_current_user)):
    """Chat over vendor documents with RAG context and two memory layers.

    SHORT-TERM: the last chat_history_window persisted messages are
    replayed into the prompt so follow-ups resolve.  LONG-TERM: mem0
    memories for this analyst are recalled semantically before the call,
    and the finished exchange is handed to mem0 for fact extraction in
    the background (never delays the response).
    """
    try:
        settings = get_settings()
        history = build_history_messages(
            get_chat_history(req.assessment_id), settings.chat_history_window
        )
        memories = await asyncio.to_thread(recall, user_id, req.question)

        reply, sources = await chat_with_docs(
            question=req.question,
            assessment_id=req.assessment_id,
            context=req.context,
            history=history,
            memories=memories,
        )

        # Persist chat history (citations saved with assistant message)
        save_chat_message(req.assessment_id, "user", req.question)
        save_chat_message(
            req.assessment_id, "assistant", reply,
            [s.model_dump() for s in sources],
        )

        # Long-term extraction in the background — remember() never raises.
        task = asyncio.create_task(
            asyncio.to_thread(remember, user_id, req.question, reply)
        )
        _bg_tasks.add(task)
        task.add_done_callback(_bg_tasks.discard)

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
