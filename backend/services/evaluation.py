"""
Layer 3: Control Evaluation — scores vendor documents against NIST controls.

RESPONSIBILITY:
    Takes one security control dict and an assessment_id, retrieves relevant
    document chunks, builds the scoring prompt from controls.py, sends it
    to the OpenRouter LLM, and parses the JSON response into a ControlResult.

    This is where the LLM is actually called.  No other service file
    should call the LLM directly (except chat.py for chat).

    evaluate_all_controls() runs the 20 controls in 5 sequential
    batches of 4, sleeping 1 s between batches and emitting an SSE
    progress update after each batch.

IMPORTS FROM: models/controls (get_all_controls, get_scoring_prompt),
              models/schemas (ControlResult, Citation, ControlScore),
              services/retrieval, config
IMPORTED BY:  mcp/server.py, chains/assessment_graph.py
"""

import json
import logging
import re
import time

from openai import OpenAI

from config import get_settings
from models.controls import get_all_controls, get_scoring_prompt
from models.schemas import ControlResult, Citation, ControlScore
from services.progress import set_progress
from services.retrieval import search_documents

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Return a module-level singleton OpenAI client (reuses HTTP connections)."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
    return _client


def _parse_confidence(raw) -> float:
    """Clamp the LLM's confidence value to [0.0, 1.0].

    Handles floats, ints, and legacy HIGH/MEDIUM/LOW strings gracefully.
    """
    _legacy = {"HIGH": 0.85, "MEDIUM": 0.5, "LOW": 0.15}
    if isinstance(raw, str) and raw.upper() in _legacy:
        return _legacy[raw.upper()]
    try:
        return max(0.0, min(1.0, float(raw)))
    except (TypeError, ValueError):
        return 0.5


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
            "confidence": 0.0,
            "evidence_quote": None,
            "evidence_chunk": None,
            "reasoning": "Unable to evaluate — document evidence was insufficient or the model timed out. Try re-running the assessment.",
            "gap": "Could not evaluate — retry may help",
        }


def evaluate_control(control: dict, assessment_id: str) -> ControlResult:
    """Evaluate a single security control against an assessment's documents.

    Steps:
    1. Search for relevant document chunks using the control's search_query
    2. Build the scoring prompt via get_scoring_prompt()
    3. Send to OpenRouter LLM
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

    if len(results) == 0:
        results = search_documents(
            query=control["title"],
            assessment_id=assessment_id,
            top_k=settings.retrieval_top_k,
        )
        logger.info("Control %s: zero chunks on first query, retried with title", control_id)

    logger.debug(
        "Control %s retrieved %d chunks, scores: %s",
        control_id,
        len(results),
        [round(r["score"], 3) for r in results],
    )

    # Extract just the text content for the prompt
    chunk_texts = [r["content"] for r in results]

    # 2. Build the scoring prompt from controls.py
    prompt = get_scoring_prompt(control, chunk_texts)

    # 3. Call the LLM
    client = _get_client()
    try:
        response = client.chat.completions.create(
            model=settings.openrouter_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        raw_output = response.choices[0].message.content
    except Exception as e:
        logger.error(f"LLM call failed for {control_id}: {e}")
        raw_output = json.dumps({
            "control_id": control_id,
            "score": "NO_EVIDENCE",
            "confidence": 0.0,
            "evidence_quote": None,
            "evidence_chunk": None,
            "reasoning": "Model call failed due to rate limiting. Re-run the assessment to retry this control.",
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
        confidence=_parse_confidence(parsed.get("confidence", 0.5)),
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
    """Evaluate all 20 security controls in sequential batches.

    Processes controls in batches of 4 (5 batches for 20 controls).
    Each batch is run sequentially (no thread pool) to keep request
    rate predictable for the LLM provider.  Between batches we sleep
    1 second to smooth out rate-limit bursts.

    After every batch, set_progress() pushes an SSE update so the
    frontend sees granular evaluation progress (45% to 85% across
    the 5 batches).

    Args:
        assessment_id: Which assessment's documents to evaluate against.

    Returns:
        List of ControlResult objects (one per control), sorted by control_id.
    """
    controls = get_all_controls()
    total = len(controls)
    logger.info(
        f"Starting evaluation of {total} controls "
        f"for assessment {assessment_id}"
    )

    BATCH_SIZE = 3
    results: list[ControlResult] = []

    for batch_num, start in enumerate(range(0, total, BATCH_SIZE)):
        batch = controls[start:start + BATCH_SIZE]
        for i, control in enumerate(batch):
            results.append(evaluate_control(control, assessment_id))
            if i < len(batch) - 1:
                time.sleep(2)

        first_idx = batch_num * BATCH_SIZE + 1
        last_idx = min(batch_num * BATCH_SIZE + BATCH_SIZE, total)
        set_progress(
            assessment_id,
            "evaluating",
            f"Evaluating controls {first_idx}–{last_idx} of {total}...",
            55 + (batch_num + 1) * 5,
        )

        # Smooth out rate-limit bursts; skip after the last batch
        if start + BATCH_SIZE < total:
            time.sleep(5)

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
