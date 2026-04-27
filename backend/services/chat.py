"""Layer 3: RAG Chat — chat over vendor documents using LangChain + Groq.

RESPONSIBILITY:
    Two capabilities:
    1. chat_with_docs() — RAG chat: retrieve relevant chunks from Qdrant,
       build a grounded prompt, send to Groq Llama, return answer + citations.
    2. generate_summary() — Generate an executive summary from assessment data.

    No database writes, no vector operations.  Retrieval is delegated to
    services/retrieval.search_documents().

IMPORTS FROM: services/retrieval, models/schemas, config
IMPORTED BY:  routers/chat.py, mcp/server.py
"""

import asyncio
import logging
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from config import get_settings
from services.retrieval import search_documents
from models.schemas import Citation

logger = logging.getLogger(__name__)


async def chat_with_docs(
    question: str,
    assessment_id: str,
    context: str | None = None,
) -> tuple[str, list[Citation]]:
    """RAG chat: retrieve relevant chunks from Qdrant, then ask Groq Llama."""
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
    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=0.7,
        max_tokens=800,
    )

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

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("human", "Assessment context:\n{context}\n\nQuestion: {question}"),
    ])

    # 5. Call LLM
    chain = prompt | llm
    response = await chain.ainvoke({
        "context": context or "No additional context provided.",
        "question": question,
    })

    return response.content, citations


async def generate_summary(
    vendor_name: str,
    score: int,
    risk_level: str,
    controls: list[dict],
    notes: str = "",
) -> str:
    """Generate executive summary using LLM."""
    settings = get_settings()

    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=0.7,
        max_tokens=1000,
    )

    # Format controls as readable lines instead of raw Python repr
    controls_text = "\n".join(
        f"  - {c.get('id', '?')} [{c.get('category', '')}] {c.get('name', '')}: "
        f"{c.get('status', 'unknown').upper()}"
        for c in controls[:20]
    ) if controls else "  No controls evaluated."

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a security assessment report writer. "
            "Generate a concise executive summary. Use markdown with headers and bullet points.",
        ),
        (
            "human",
            "Vendor: {vendor}\n"
            "Score: {score}/100\n"
            "Risk Level: {risk}\n"
            "Controls:\n{controls}\n"
            "Analyst Notes: {notes}\n\n"
            "Generate: executive overview, key findings, failed controls, recommendations.",
        ),
    ])

    chain = prompt | llm
    response = await chain.ainvoke({
        "vendor": vendor_name,
        "score": score,
        "risk": risk_level,
        "controls": controls_text,
        "notes": notes or "None",
    })

    return response.content
