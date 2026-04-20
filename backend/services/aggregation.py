"""
Layer 3: Score Aggregation — calculates final assessment scores.

RESPONSIBILITY:
    Takes the list of 20 scored ControlResult objects from evaluation.py,
    calls calculate_scores() from controls.py to compute domain and overall
    scores, builds a markdown gaps summary, and assembles the final
    AssessmentResponse.

    No LLM calls, no retrieval, no database writes.  Pure computation
    over already-scored results.

IMPORTS FROM: models/controls (calculate_scores),
              models/schemas (AssessmentResponse, ControlResult, RiskLevel, ControlScore)
IMPORTED BY:  mcp/server.py, chains/assessment_graph.py
"""

import logging
from models.controls import calculate_scores
from models.schemas import (
    AssessmentResponse,
    ControlResult,
    RiskLevel,
    ControlScore,
)

logger = logging.getLogger(__name__)


def _build_gaps_summary(control_results: list[ControlResult]) -> str:
    """Build a markdown summary of all controls that scored FAIL or NO_EVIDENCE.

    Groups gaps by domain for readability.  Each gap entry includes the
    control ID, title, score, and the gap description from the LLM.
    """
    # Collect controls with gaps
    gaps = [
        r for r in control_results
        if r.score in (ControlScore.FAIL, ControlScore.NO_EVIDENCE)
    ]

    if not gaps:
        return "No gaps identified — all controls passed or partially passed."

    # Group by domain
    domains: dict[str, list[ControlResult]] = {}
    for r in gaps:
        domains.setdefault(r.domain, []).append(r)

    lines = ["## Gaps Summary\n"]
    for domain, results in domains.items():
        lines.append(f"### {domain}\n")
        for r in results:
            score_label = r.score.value
            gap_text = r.gap or "No specific gap described"
            lines.append(
                f"- **{r.control_id} — {r.title}** [{score_label}]\n"
                f"  {gap_text}\n"
            )

    return "\n".join(lines)


def aggregate_results(
    assessment_id: str,
    vendor_name: str,
    control_results: list[ControlResult],
) -> AssessmentResponse:
    """Aggregate scored control results into a final assessment response.

    Steps:
    1. Convert ControlResult list to dicts for calculate_scores()
    2. Call calculate_scores() from controls.py
    3. Build markdown gaps summary
    4. Assemble and return AssessmentResponse

    Args:
        assessment_id: The assessment being aggregated.
        vendor_name: Vendor name for the response.
        control_results: List of 20 scored ControlResult objects.

    Returns:
        Complete AssessmentResponse with scores, domain breakdown, and gaps.
    """
    logger.info(
        f"Aggregating {len(control_results)} control results "
        f"for assessment {assessment_id}"
    )

    # 1. Convert to dict format that calculate_scores() expects:
    #    [{"control_id": "IAM-001", "score": "PASS"}, ...]
    results_dicts = [
        {"control_id": r.control_id, "score": r.score.value}
        for r in control_results
    ]

    # 2. Calculate domain and overall scores
    scores = calculate_scores(results_dicts)

    # 3. Build gaps summary
    gaps_summary = _build_gaps_summary(control_results)

    # 4. Map risk_level string to enum
    risk_str = scores["risk_level"]
    try:
        risk_level = RiskLevel(risk_str)
    except ValueError:
        risk_level = RiskLevel.HIGH

    logger.info(
        f"Assessment {assessment_id}: "
        f"overall={scores['overall_score']}%, risk={risk_level.value}"
    )

    return AssessmentResponse(
        assessment_id=assessment_id,
        vendor_name=vendor_name,
        overall_score=scores["overall_score"],
        risk_level=risk_level,
        domain_scores=scores["domain_scores"],
        control_results=control_results,
        gaps_summary=gaps_summary,
    )
