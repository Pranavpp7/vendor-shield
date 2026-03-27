"""Per-control evidence retrieval from Pinecone."""

from services.pinecone_store import search
from models.schemas import Citation
import logging

logger = logging.getLogger(__name__)


def retrieve_evidence_for_control(
    assessment_id: str,
    control_name: str,
    top_k: int = 24,
    max_unique_docs: int = 8,
) -> tuple[str, list[Citation]]:
    """Retrieve the most relevant evidence chunks for a single control.

    Returns:
        Tuple of (formatted evidence string, list of citations)
    """
    results = search(assessment_id, control_name, top_k=top_k)

    if not results:
        return "NO EVIDENCE FOUND IN DOCUMENTS", []

    # Deduplicate: keep best chunk per document, up to max_unique_docs
    seen_docs: dict[str, dict] = {}
    for r in results:
        doc_name = r["document_name"]
        if doc_name not in seen_docs:
            seen_docs[doc_name] = r
        if len(seen_docs) >= max_unique_docs:
            break

    # Format evidence and citations
    evidence_lines = []
    citations = []
    for doc_name, r in seen_docs.items():
        score_pct = int(r["score"] * 100)
        evidence_lines.append(
            f"[{r['document_name']}, Page {r['page_number']}, Section {r['chunk_index'] + 1}, "
            f"{score_pct}% match]: {r['content'][:500]}"
        )
        citations.append(Citation(
            document=r["document_name"],
            page=r["page_number"],
            excerpt=r["content"][:200],
            similarity=r["score"],
        ))

    return "\n".join(evidence_lines), citations


def retrieve_rag_context(
    assessment_id: str,
    query: str,
    top_k: int = 8,
) -> str:
    """Retrieve RAG context for chat or summary generation."""
    results = search(assessment_id, query, top_k=top_k)

    if not results:
        return ""

    context_lines = ["\n--- RETRIEVED DOCUMENT CONTEXT ---"]
    for r in results:
        score_pct = int(r["score"] * 100)
        context_lines.append(
            f"[Source: {r['document_name']}, Page {r['page_number']}, "
            f"Relevance: {score_pct}%]:\n{r['content']}"
        )
    context_lines.append("--- END DOCUMENT CONTEXT ---\n")

    return "\n\n".join(context_lines)
