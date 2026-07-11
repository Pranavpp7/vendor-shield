"""Layer 3: RAG Chat — chat over vendor documents using LangChain + OpenRouter.

RESPONSIBILITY:
    Two capabilities:
    1. chat_with_docs() — RAG chat: retrieve relevant chunks from Qdrant,
       build a grounded prompt, send to OpenRouter Llama, return answer + citations.
    2. generate_summary() — Generate an executive summary from assessment data.

    No database writes, no vector operations.  Retrieval is delegated to
    services/retrieval.search_documents().

IMPORTS FROM: services/retrieval, models/schemas, config
IMPORTED BY:  routers/chat.py, mcp/server.py
"""

import asyncio
import logging
from openai import OpenAI
from config import get_settings
from services.retrieval import search_documents
from models.schemas import Citation

logger = logging.getLogger(__name__)


async def chat_with_docs(
    question: str,
    assessment_id: str,
    context: str | None = None,
) -> tuple[str, list[Citation]]:
    """RAG chat: retrieve relevant chunks from Qdrant, then ask OpenRouter Llama."""
    settings = get_settings()

    # 1. Retrieve relevant document chunks (search_documents is sync — run in thread)
    results = await asyncio.to_thread(
        search_documents,
        question,
        assessment_id,
        settings.retrieval_top_k,
    )

    # 2. Build RAG context string from retrieved chunks
    rag_context = ""
    if results:
        chunk_lines = [
            f"[Source: {r['document_name']}, Chunk {r['chunk_index']}]\n{r['content']}"
            for r in results
        ]
        rag_context = "\n\n---\n\n".join(chunk_lines)

    # 3. Build citations from the same results
    citations = [
        Citation(
            document=r["document_name"],
            excerpt=r["content"][:200],
            similarity=r["score"],
        )
        for r in results
    ]

    # 4. Build LLM prompt
    system_message = (
        "You are a security assessment assistant. "
        "You MUST answer ONLY from the document context provided below. "
        "Do NOT use general knowledge, training data, or outside information. "
        "If the answer is not explicitly present in the provided document context, "
        "you MUST respond with exactly: "
        "'I could not find this information in the vendor documents.' "
        "Never guess or infer beyond what the documents state. "
        "Keep responses concise and professional. Use bullet points where appropriate."
    )
    if rag_context:
        system_message += (
            "\n\nDocument context retrieved from vendor files:\n\n"
            + rag_context
            + "\n\nOnly answer using the above document context. "
            "Always cite the source document name when referencing information."
        )
    else:
        system_message += (
            "\n\nNo relevant document content was retrieved for this question. "
            "You must respond: 'I could not find this information in the vendor documents.'"
        )

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": f"Assessment context:\n{context or 'No additional context provided.'}\n\nQuestion: {question}"},
    ]

    # 5. Call LLM
    client = OpenAI(api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url)
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model=settings.openrouter_model,
        messages=messages,
        temperature=0.1,
        max_tokens=800,
    )

    return response.choices[0].message.content, citations


async def generate_summary(
    vendor_name: str,
    score: int,
    risk_level: str,
    controls: list[dict],
    notes: str = "",
) -> str:
    """Generate executive summary using LLM."""
    settings = get_settings()

    # Consistent terminology contract — must match the rest of the app:
    # "Failed" is reserved for VERIFIED deficiencies; unverified controls
    # are "Needs Info", never "failed".
    _LABELS = {
        "passed": "PASSED",
        "partial": "PARTIAL",
        "failed": "FAILED",
        "needs_info": "NEEDS INFO (unverified — no evidence provided)",
    }
    controls_text = "\n".join(
        f"  - {c.get('id', '?')} [{c.get('category', '')}] {c.get('name', '')}: "
        f"{_LABELS.get(c.get('status', ''), str(c.get('status', 'unknown')).upper())}"
        for c in controls[:40]
    ) if controls else "  No controls evaluated."

    counts = {s: sum(1 for c in controls if c.get("status") == s)
              for s in ("passed", "partial", "failed", "needs_info")}

    messages = [
        {
            "role": "system",
            "content": (
                "You are a security assessment report writer. Generate a concise "
                "executive summary in markdown with headers and bullet points.\n\n"
                "TERMINOLOGY RULES (strict):\n"
                "- 'Failed' means a VERIFIED deficiency — evidence proved the "
                "vendor does not meet the control. Only controls marked FAILED "
                "may ever appear under a failed/deficient heading.\n"
                "- NEEDS INFO means the documents contained no evidence either "
                "way. These are documentation gaps to chase, NOT failures — "
                "never describe them as failed, deficient, or non-compliant.\n"
                "- Do not invent findings beyond the control list given."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Vendor: {vendor_name}\n"
                f"Score: {score}/100 (unverified controls count as 0)\n"
                f"Risk Level: {risk_level}\n"
                f"Status counts: {counts['passed']} passed, {counts['partial']} partial, "
                f"{counts['failed']} failed, {counts['needs_info']} needs info\n"
                f"Controls:\n{controls_text}\n"
                f"Analyst Notes: {notes or 'None'}\n\n"
                "Generate these sections:\n"
                "1. Executive Overview\n"
                "2. Key Findings\n"
                "3. Confirmed Gaps — FAILED controls only; if none, state "
                "'No verified control failures.'\n"
                "4. Unverified Controls (Needs Info) — list them as evidence "
                "to request from the vendor\n"
                "5. Recommendations"
            ),
        },
    ]

    client = OpenAI(api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url)
    response = await asyncio.to_thread(
        client.chat.completions.create,
        model=settings.openrouter_model,
        messages=messages,
        temperature=0.2,  # report writing wants consistency, not creativity
        max_tokens=1200,
    )

    return response.choices[0].message.content
