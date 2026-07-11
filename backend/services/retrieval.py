"""
Layer 3: Document Retrieval (Semantic Search).

RESPONSIBILITY:
    Takes a text query, embeds it, and searches the assessment's Qdrant
    collection for the most similar document chunks.  Returns results
    with source document names so evaluation.py can build citations.

    This is intentionally a thin wrapper around embedding + qdrant_store.
    The value is a single clean interface for callers — they don't need
    to know about embedding or Qdrant separately.  Also makes it easy
    to swap to hybrid search later without changing callers.

IMPORTS FROM: services/embedding, storage/qdrant_store
IMPORTED BY:  services/evaluation.py, services/chat.py, mcp/server.py
"""

import logging
import math
from collections import OrderedDict

from services.embedding import embed_query
from storage.qdrant_store import similarity_search

logger = logging.getLogger(__name__)

# How many candidates to pull from Qdrant before diversifying down to top_k.
POOL_MULTIPLIER = 3

# Similarity multiplier for chunks from "reference" documents (generic
# guidance/marketing the user tagged at upload) — vendor-authored evidence
# should outrank generic material of equal semantic similarity.
REFERENCE_WEIGHT = 0.85


def apply_doc_type_weights(results: list[dict]) -> list[dict]:
    """Down-weight reference-document chunks, then re-sort by score.

    Mutates scores in place (retrieval results are per-call dicts).
    Chunks ingested before doc-type tagging have no doc_type and are
    treated as vendor-authored.
    """
    for r in results:
        if r.get("doc_type") == "reference":
            r["score"] = r["score"] * REFERENCE_WEIGHT
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def diversify_by_document(results: list[dict], top_k: int) -> list[dict]:
    """Select top_k results with guaranteed document diversity.

    Pure global cosine top-k lets one keyword-dense document monopolize
    every slot (measured on a real assessment: a generic buyer's-guide
    whitepaper won 71% of all evidence slots and was the #1 chunk for
    18 of 20 controls, starving the vendor's actual evidence docs).

    Selection: round-robin across documents (documents ordered by their
    best chunk's similarity, chunks within a document by similarity),
    with any single document capped at ceil(top_k / 2) when multiple
    documents are present.  If the cap leaves slots unfilled, they are
    topped up by raw similarity so callers always get top_k when enough
    candidates exist.  Final list is re-sorted by similarity.
    """
    if len(results) <= top_k:
        return results

    # Group by document, preserving similarity order within each group
    by_doc: "OrderedDict[str, list[dict]]" = OrderedDict()
    for r in results:  # results arrive sorted by similarity desc
        by_doc.setdefault(r["document_name"], []).append(r)

    cap = top_k if len(by_doc) == 1 else math.ceil(top_k / 2)
    selected: list[dict] = []
    taken = {doc: 0 for doc in by_doc}

    # Round-robin: one chunk per document per round
    while len(selected) < top_k:
        progressed = False
        for doc, chunks in by_doc.items():
            if len(selected) >= top_k:
                break
            if taken[doc] < min(cap, len(chunks)):
                selected.append(chunks[taken[doc]])
                taken[doc] += 1
                progressed = True
        if not progressed:
            break  # every document exhausted or capped

    # Top-up past the cap if we still have room and candidates
    if len(selected) < top_k:
        chosen = {id(r) for r in selected}
        for r in results:
            if len(selected) >= top_k:
                break
            if id(r) not in chosen:
                selected.append(r)

    selected.sort(key=lambda r: r["score"], reverse=True)
    return selected


def search_documents(
    query: str,
    assessment_id: str,
    top_k: int = 8,
) -> list[dict]:
    """Search an assessment's documents for chunks matching a query.

    Retrieval is document-diversified: a deeper candidate pool is pulled
    from Qdrant, then top_k slots are filled round-robin across source
    documents (see diversify_by_document) so every uploaded document's
    strongest evidence reaches the LLM judge.

    Args:
        query: Natural language search text (e.g. a control's search_query
               or a user's chat question).
        assessment_id: Which assessment's documents to search.
        top_k: Maximum number of results to return.

    Returns:
        List of dicts sorted by relevance (most relevant first), each with:
        - "content": the chunk text
        - "document_name": source filename or URL (for citations)
        - "chunk_index": position within the source document
        - "score": cosine similarity score (0.0 to 1.0)

        Returns empty list if no collection exists or no matches found.
    """
    # 1. Embed the query (with BGE search prefix)
    query_vector = embed_query(query)

    # 2. Pull a deeper pool, down-weight reference docs, diversify across docs
    pool = similarity_search(assessment_id, query_vector, top_k * POOL_MULTIPLIER)
    pool = apply_doc_type_weights(pool)
    results = diversify_by_document(pool, top_k)

    logger.info(
        f"Retrieved {len(results)} of {len(pool)} candidate chunks for query "
        f"(assessment={assessment_id}, top_k={top_k}, "
        f"docs={len({r['document_name'] for r in results})})"
    )
    return results
