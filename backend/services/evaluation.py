"""
Layer 3: Control Evaluation — scores vendor documents against framework controls.

RESPONSIBILITY:
    Takes one security control dict and an assessment_id, retrieves relevant
    document chunks, builds the scoring prompt from controls.py, sends it
    to the OpenRouter LLM, and parses the JSON response into a ControlResult.

    This is where the LLM is actually called.  No other service file
    should call the LLM directly (except chat.py for chat and
    followup.py / framework_extraction.py for their features).

    evaluate_all_controls() scores every control CONCURRENTLY with an
    asyncio semaphore bounding in-flight LLM calls (llm_concurrency in
    config).  All I/O is async or pushed to a thread, so the FastAPI
    event loop is never blocked during an assessment run.

    LLM calls request JSON mode (response_format json_object) so the
    model returns machine-parseable output; if the provider rejects the
    parameter, the call transparently retries without it, and
    _parse_llm_json() remains as the last line of defense either way.

IMPORTS FROM: models/controls (get_all_controls, get_scoring_prompt),
              models/schemas (ControlResult, Citation, ControlScore),
              services/retrieval, config
IMPORTED BY:  mcp/server.py
"""

import asyncio
import json
import logging
import re

from openai import AsyncOpenAI

from config import get_settings
from models.controls import get_all_controls, get_scoring_prompt
from models.schemas import ControlResult, Citation, ControlScore
from services.progress import set_progress
from services.retrieval import search_documents

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    """Return a module-level singleton AsyncOpenAI client (reuses HTTP connections)."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncOpenAI(
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


async def _call_llm_json(prompt: str) -> str:
    """One LLM call in JSON mode, falling back to plain mode if the
    provider rejects response_format (support varies across OpenRouter
    providers for the same model)."""
    settings = get_settings()
    client = _get_client()
    try:
        response = await client.chat.completions.create(
            model=settings.openrouter_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        if "response_format" not in str(e).lower() and "json" not in str(e).lower():
            raise
        logger.warning(f"JSON mode rejected by provider, retrying without: {e}")
        response = await client.chat.completions.create(
            model=settings.openrouter_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
    return response.choices[0].message.content or ""


async def evaluate_control(control: dict, assessment_id: str) -> ControlResult:
    """Evaluate a single security control against an assessment's documents.

    Steps:
    1. Search for relevant document chunks using the control's search_query
       (retrieval is sync CPU/network work — pushed to a worker thread)
    2. Build the scoring prompt via get_scoring_prompt()
    3. Send to OpenRouter LLM in JSON mode
    4. Parse JSON response into a ControlResult

    Args:
        control: A control dict from controls.py (has id, search_query, etc.)
        assessment_id: Which assessment's documents to search.

    Returns:
        A ControlResult with the LLM's score, evidence, reasoning, and gap.
    """
    control_id = control["id"]
    logger.info(f"Evaluating control {control_id}: {control['title']}")

    # 1. Retrieve relevant document chunks (sync embedding + Qdrant → thread)
    settings = get_settings()
    results = await asyncio.to_thread(
        search_documents,
        query=control["search_query"],
        assessment_id=assessment_id,
        top_k=settings.retrieval_top_k,
    )

    if len(results) == 0:
        results = await asyncio.to_thread(
            search_documents,
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
    try:
        raw_output = await _call_llm_json(prompt)
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


async def evaluate_all_controls(
    assessment_id: str,
    framework_id: str | None = None,
) -> list[ControlResult]:
    """Evaluate every control of a framework concurrently.

    In-flight LLM calls are bounded by an asyncio.Semaphore
    (settings.llm_concurrency) to keep the request rate predictable for
    the provider.  A failed control never sinks the run — evaluate_control
    degrades to a NO_EVIDENCE result on LLM errors.

    Args:
        assessment_id: Which assessment's documents to evaluate against.
        framework_id: Which control framework to use (default NIST SP 800-53).

    Returns:
        List of ControlResult objects (one per control), sorted by control_id.
    """
    controls = get_all_controls(framework_id)
    settings = get_settings()
    total = len(controls)
    logger.info(
        f"Starting evaluation of {total} controls "
        f"for assessment {assessment_id} "
        f"(concurrency={settings.llm_concurrency})"
    )

    semaphore = asyncio.Semaphore(settings.llm_concurrency)
    done = 0
    set_progress(assessment_id, "evaluate", f"Scoring controls (0/{total})…", 30)

    async def _bounded(control: dict) -> ControlResult:
        nonlocal done
        async with semaphore:
            result = await evaluate_control(control, assessment_id)
        # Per-control progress for the SSE pipeline view (30% → 85%)
        done += 1
        set_progress(
            assessment_id, "evaluate",
            f"Scoring controls ({done}/{total})…",
            30 + int(55 * done / total),
        )
        return result

    results = list(await asyncio.gather(*[_bounded(c) for c in controls]))

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
