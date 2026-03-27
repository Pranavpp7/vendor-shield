"""Score aggregation and summary generation."""

import logging
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from config import get_settings
from models.schemas import ControlResult, ControlStatus, DomainScore, RiskLevel

logger = logging.getLogger(__name__)


def compute_scores(results: list[ControlResult]) -> tuple[int, RiskLevel, list[DomainScore]]:
    """Compute overall score, risk level, and per-domain scores."""

    # Status weights for scoring
    STATUS_SCORE = {
        ControlStatus.PASS: 1.0,
        ControlStatus.PARTIAL: 0.5,
        ControlStatus.FAIL: 0.0,
        ControlStatus.NO_EVIDENCE: 0.0,
    }

    # Overall score (weighted)
    total_weight = 0
    weighted_score = 0
    for r in results:
        weight = 1.0  # could be per-control weight
        total_weight += weight
        weighted_score += STATUS_SCORE[r.status] * weight

    overall_score = int((weighted_score / total_weight * 100)) if total_weight > 0 else 0

    # Risk level
    if overall_score >= 70:
        risk_level = RiskLevel.LOW
    elif overall_score >= 40:
        risk_level = RiskLevel.MEDIUM
    else:
        risk_level = RiskLevel.HIGH

    # Domain scores
    categories: dict[str, list[ControlResult]] = {}
    for r in results:
        categories.setdefault(r.category, []).append(r)

    domain_scores = []
    for domain, controls in categories.items():
        passed = sum(1 for c in controls if c.status == ControlStatus.PASS)
        partial = sum(1 for c in controls if c.status == ControlStatus.PARTIAL)
        failed = sum(1 for c in controls if c.status == ControlStatus.FAIL)
        no_ev = sum(1 for c in controls if c.status == ControlStatus.NO_EVIDENCE)
        total = len(controls)
        score = int((passed + partial * 0.5) / total * 100) if total > 0 else 0

        domain_scores.append(DomainScore(
            domain=domain,
            score=score,
            total_controls=total,
            passed=passed,
            partial=partial,
            failed=failed,
            no_evidence=no_ev,
        ))

    return overall_score, risk_level, domain_scores


def generate_gaps_summary(results: list[ControlResult]) -> str:
    """Generate a text summary of gaps (non-passing controls)."""
    gaps = [r for r in results if r.status != ControlStatus.PASS]
    if not gaps:
        return "No gaps identified. All controls passed."

    lines = ["## Gaps Identified\n"]
    for r in gaps:
        status_emoji = {"Partial": "⚠️", "Fail": "❌", "No Evidence": "❓"}.get(r.status.value, "")
        lines.append(f"- {status_emoji} **{r.name}** ({r.category}): {r.status.value} — {r.rationale}")

    return "\n".join(lines)


async def generate_executive_summary(
    vendor_name: str,
    score: int,
    risk_level: str,
    results: list[ControlResult],
    notes: str = "",
) -> str:
    """Use LLM to generate executive summary."""
    settings = get_settings()
    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=0.7,
        max_tokens=1000,
    )

    controls_summary = []
    for r in results:
        controls_summary.append(f"{r.id} ({r.category}): {r.name} → {r.status.value} — {r.rationale}")

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a security assessment report writer. Generate a concise executive summary. Use markdown with headers and bullet points."),
        ("human", "Vendor: {vendor}\nScore: {score}/100\nRisk Level: {risk}\nControls:\n{controls}\nNotes: {notes}\n\nGenerate: executive overview, key findings, failed controls, recommendations."),
    ])

    chain = prompt | llm
    response = await chain.ainvoke({
        "vendor": vendor_name,
        "score": score,
        "risk": risk_level,
        "controls": "\n".join(controls_summary),
        "notes": notes or "None",
    })

    return response.content
