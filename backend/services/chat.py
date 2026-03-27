"""RAG chat service — chat over vendor documents using LangChain + Groq."""

import logging
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from config import get_settings
from services.retrieval import retrieve_rag_context
from models.schemas import Citation
from services.pinecone_store import search

logger = logging.getLogger(__name__)


async def chat_with_docs(
    question: str,
    assessment_id: str,
    context: str | None = None,
) -> tuple[str, list[Citation]]:
    """RAG chat: retrieve relevant chunks from Pinecone, then ask Groq Llama."""
    settings = get_settings()

    # Retrieve RAG context
    rag_context = retrieve_rag_context(assessment_id, question, top_k=8)

    # Get source citations
    results = search(assessment_id, question, top_k=5)
    citations = [
        Citation(
            document=r["document_name"],
            page=r["page_number"],
            excerpt=r["content"][:200],
            similarity=r["score"],
        )
        for r in results
    ]

    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=0.7,
        max_tokens=800,
    )

    system_message = (
        "You are a security assessment assistant. Provide clear, professional analysis "
        "based on the vendor assessment data. Keep responses concise and actionable. "
        "Use bullet points where appropriate."
    )
    if rag_context:
        system_message += (
            "\n\nUse the following uploaded document evidence to provide grounded, evidence-based answers. "
            "Always cite the source document name when referencing information from documents."
            + rag_context
        )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("human", "Assessment context:\n{context}\n\nQuestion: {question}"),
    ])

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

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a security assessment report writer. Generate a concise executive summary. Use markdown with headers and bullet points."),
        ("human", "Vendor: {vendor}\nScore: {score}/100\nRisk Level: {risk}\nControls: {controls}\nNotes: {notes}\n\nGenerate: executive overview, key findings, failed controls, recommendations."),
    ])

    chain = prompt | llm
    response = await chain.ainvoke({
        "vendor": vendor_name,
        "score": score,
        "risk": risk_level,
        "controls": str(controls),
        "notes": notes or "None",
    })

    return response.content
