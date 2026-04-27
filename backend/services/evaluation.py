"""
Layer 3: Control Evaluation — scores vendor documents against NIST controls.

RESPONSIBILITY:
    Takes one security control dict and an assessment_id, retrieves relevant
    document chunks, builds the scoring prompt from controls.py, sends it
    to the Groq LLM, and parses the JSON response into a ControlResult.

    This is where the LLM is actually called.  No other service file
    should call the LLM directly (except chat.py for chat).

    evaluate_all_controls() runs all 20 controls concurrently for speed
    (10-15x faster than sequential).

IMPORTS FROM: models/controls (get_all_controls, get_scoring_prompt),
              models/schemas (ControlResult, Citation, ControlScore),
              services/retrieval, config
IMPORTED BY:  mcp/server.py, chains/assessment_graph.py
"""

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

from config import get_settings
from models.controls import get_all_controls, get_scoring_prompt
from models.schemas import ControlResult, Citation, ControlScore
from services.retrieval import search_documents

logger = logging.getLogger(__name__)


def _get_llm() -> ChatGroq:
    """Create a ChatGroq LLM instance from config settings."""
    settings = get_settings()
    return ChatGroq(
        api_key=settings.groq_api_key,
        model_name=settings.groq_model,
        temperature=0.0,  # deterministic scoring
    )


def _parse_llm_json(raw: str, control_id: str) -> dict:
    """Parse the LLM's JSON response, handling common formatting issues.

    Strips markdown fences, handles partial JSON, and returns a dict.
    On failure, returns a fallback dict with NO_EVIDENCE score.
    """
    # Strip markdown code fences if present
    cleaned = re.sub(r"```json\s*", "", raw)
    cleaned = re.sub(r"```\s*$", "", cleaned)
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error(
            f"Failed to parse LLM JSON for {control_id}. "
            f"Raw output: {raw[:500]}"
        )
        return {
            "control_id": control_id,
            "score": "NO_EVIDENCE",
            "confidence": "LOW",
            "evidence_quote": None,
            "evidence_chunk": None,
            "reasoning": "LLM returned unparseable response",
            "gap": "Could not evaluate — retry may help",
        }


def evaluate_control(control: dict, assessment_id: str) -> ControlResult:
    """Evaluate a single security control against an assessment's documents.

    Steps:
    1. Search for relevant document chunks using the control's search_query
    2. Build the scoring prompt via get_scoring_prompt()
    3. Send to Groq LLM
    4. Parse JSON response into a ControlResult

    Args:
        control: A control dict from controls.py (has id, search_query, etc.)
        assessment_id: Which assessment's documents to search.

    Returns:
        A ControlResult with the LLM's score, evidence, reasoning, and gap.
    """
    control_id = control["id"]
    logger.info(f"Evaluating control {control_id}: {control['title']}")

    # 1. Retrieve relevant document chunks
    settings = get_settings()
    results = search_documents(
        query=control["search_query"],
        assessment_id=assessment_id,
        top_k=settings.retrieval_top_k,
    )

    # Extract just the text content for the prompt
    chunk_texts = [r["content"] for r in results]

    # 2. Build the scoring prompt from controls.py
    prompt = get_scoring_prompt(control, chunk_texts)

    # 3. Call the LLM
    llm = _get_llm()
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        raw_output = response.content
    except Exception as e:
        logger.error(f"LLM call failed for {control_id}: {e}")
        raw_output = json.dumps({
            "control_id": control_id,
            "score": "NO_EVIDENCE",
            "confidence": "LOW",
            "evidence_quote": None,
            "evidence_chunk": None,
            "reasoning": f"LLM call failed: {str(e)[:200]}",
            "gap": "Could not evaluate due to LLM error",
        })

    # 4. Parse the JSON response
    parsed = _parse_llm_json(raw_output, control_id)

    # 5. Build citations from the search results
    citations = [
        Citation(
            document=r["document_name"],
            excerpt=r["content"][:200],
            similarity=r["score"],
        )
        for r in results
    ]

    # 6. Build and return the ControlResult
    # Validate score value — default to NO_EVIDENCE if unrecognized
    score_raw = parsed.get("score", "NO_EVIDENCE").upper()
    try:
        score = ControlScore(score_raw)
    except ValueError:
        logger.warning(f"Unrecognized score '{score_raw}' for {control_id}")
        score = ControlScore.NO_EVIDENCE

    result = ControlResult(
        control_id=control_id,
        score=score,
        confidence=parsed.get("confidence", "MEDIUM"),
        evidence_quote=parsed.get("evidence_quote"),
        evidence_chunk=parsed.get("evidence_chunk"),
        reasoning=parsed.get("reasoning", ""),
        gap=parsed.get("gap"),
        domain=control["domain"],
        title=control["title"],
        citations=citations,
    )

    logger.info(f"Control {control_id} scored: {result.score.value}")
    return result


def evaluate_all_controls(assessment_id: str) -> list[ControlResult]:
    """Evaluate all 20 security controls concurrently.

    Uses a thread pool to run evaluations in parallel, giving
    a 10-15x speedup over sequential execution.

    Args:
        assessment_id: Which assessment's documents to evaluate against.

    Returns:
        List of 20 ControlResult objects (one per control).
    """
    controls = get_all_controls()
    logger.info(
        f"Starting evaluation of {len(controls)} controls "
        f"for assessment {assessment_id}"
    )

    # Run evaluations concurrently using threads
    # (Groq API calls are I/O-bound, so threads work well)
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(evaluate_control, control, assessment_id)
            for control in controls
        ]
        results = [f.result() for f in futures]

    # Sort by control_id for consistent ordering
    results.sort(key=lambda r: r.control_id)

    pass_count = sum(1 for r in results if r.score == ControlScore.PASS)
    partial_count = sum(1 for r in results if r.score == ControlScore.PARTIAL)
    fail_count = sum(1 for r in results if r.score == ControlScore.FAIL)
    no_ev_count = sum(1 for r in results if r.score == ControlScore.NO_EVIDENCE)

    logger.info(
        f"Evaluation complete: {pass_count} PASS, {partial_count} PARTIAL, "
        f"{fail_count} FAIL, {no_ev_count} NO_EVIDENCE"
    )
    return results
