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
from datetime import datetime, timezone
from models.controls import calculate_scores
from models.schemas import (
    AssessmentResponse,
    ControlResult,
    RiskLevel,
    ControlScore,
)

logger = logging.getLogger(__name__)


def build_gaps_summary(control_results: list[ControlResult]) -> str:
    """Build a markdown summary of all controls that scored FAIL or NO_EVIDENCE.

    Uses the effective (override-aware) score.  Groups gaps by domain for
    readability.  Each gap entry includes the control ID, title, score,
    and the gap description from the LLM.
    """
    # Collect controls with gaps
    gaps = [
        r for r in control_results
        if r.effective in (ControlScore.FAIL, ControlScore.NO_EVIDENCE)
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
            score_label = r.effective.value
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
    framework_id: str | None = None,
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

    # 1. Convert to dict format that calculate_scores() expects.
    #    The effective (override-aware) score is what gets aggregated.
    results_dicts = [
        {"control_id": r.control_id, "score": r.effective.value}
        for r in control_results
    ]

    # 2. Calculate domain and overall scores against the framework's domains
    scores = calculate_scores(results_dicts, framework_id)

    # 3. Build gaps summary
    gaps_summary = build_gaps_summary(control_results)

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
        created_at=datetime.now(timezone.utc).isoformat(),
        framework_id=framework_id or "nist-800-53",
        coverage=scores.get("coverage"),
        verified_score=scores.get("verified_score"),
        verified_controls=scores.get("verified_controls"),
        total_controls=scores.get("total_controls"),
    )


# ---------------------------------------------------------------------------
# Inherent & residual risk (vendor relationship tiering)
# ---------------------------------------------------------------------------
# Inherent risk describes the vendor RELATIONSHIP before any controls are
# considered: what data they touch, how critical they are, how deep their
# access goes.  Residual risk combines the assessed control posture with
# that inherent tier — a weak vendor with no data access matters less than
# a mediocre vendor holding all your PII.

_PROFILE_POINTS = {"low": 1, "moderate": 2, "high": 3}

# (min_total_points, tier) — evaluated top-down.  Total ranges 3–9.
_INHERENT_TIERS = [
    (8, "Critical"),
    (6, "High"),
    (5, "Moderate"),
    (3, "Low"),
]

# residual = _RESIDUAL_MATRIX[inherent_tier][assessed_risk_level]
_RESIDUAL_MATRIX = {
    "Low":      {"Low": "Low",    "Medium": "Low",    "High": "Medium"},
    "Moderate": {"Low": "Low",    "Medium": "Medium", "High": "High"},
    "High":     {"Low": "Medium", "Medium": "High",   "High": "High"},
    "Critical": {"Low": "Medium", "Medium": "High",   "High": "Critical"},
}


def compute_inherent_risk(profile: dict) -> dict:
    """Score an intake profile into an inherent-risk tier.

    profile: {"data_sensitivity": "low|moderate|high",
              "business_criticality": ..., "access_scope": ...}

    Returns {"tier": str, "points": int, "profile": dict}.
    """
    points = sum(
        _PROFILE_POINTS.get(str(profile.get(field, "low")).lower(), 1)
        for field in ("data_sensitivity", "business_criticality", "access_scope")
    )
    tier = next(t for minimum, t in _INHERENT_TIERS if points >= minimum)
    return {"tier": tier, "points": points, "profile": profile}


def compute_residual_risk(inherent_tier: str, assessed_risk: str) -> str:
    """Combine the inherent tier with the assessed (control-based) risk level."""
    row = _RESIDUAL_MATRIX.get(inherent_tier, _RESIDUAL_MATRIX["Moderate"])
    return row.get(assessed_risk, assessed_risk)
