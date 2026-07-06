"""Aggregation: gaps summary, final response assembly, inherent/residual risk."""

from models.schemas import ControlResult, ControlScore
from services.aggregation import (
    aggregate_results,
    build_gaps_summary,
    compute_inherent_risk,
    compute_residual_risk,
)
from models.controls import get_all_controls


def _result(cid: str, score: str, **kw) -> ControlResult:
    return ControlResult(
        control_id=cid,
        score=ControlScore(score),
        domain=kw.pop("domain", "Governance & Risk"),
        title=f"Control {cid}",
        gap=kw.pop("gap", None),
        **kw,
    )


class TestGapsSummary:
    def test_no_gaps_message(self):
        summary = build_gaps_summary([_result("A-1", "PASS"), _result("A-2", "PARTIAL")])
        assert "No gaps identified" in summary

    def test_fail_and_no_evidence_listed(self):
        summary = build_gaps_summary([
            _result("A-1", "FAIL", gap="No MFA policy"),
            _result("A-2", "NO_EVIDENCE"),
            _result("A-3", "PASS"),
        ])
        assert "A-1" in summary and "No MFA policy" in summary
        assert "A-2" in summary
        assert "A-3" not in summary

    def test_override_removes_gap(self):
        fixed = _result("A-1", "FAIL")
        fixed.analyst_score = ControlScore.PASS
        assert "No gaps identified" in build_gaps_summary([fixed])

    def test_override_score_label_shown(self):
        downgraded = _result("A-1", "PASS")
        downgraded.analyst_score = ControlScore.FAIL
        summary = build_gaps_summary([downgraded])
        assert "[FAIL]" in summary


class TestAggregateResults:
    def test_full_soc2_aggregation(self):
        results = [
            _result(c["id"], "PASS", domain=c["domain"])
            for c in get_all_controls("soc2-tsc")
        ]
        response = aggregate_results("aid", "Acme", results, framework_id="soc2-tsc")
        assert response.overall_score == 100
        assert response.risk_level.value == "Low"
        assert response.framework_id == "soc2-tsc"
        assert response.coverage == 100
        assert response.verified_controls == 10
        assert response.total_controls == 10
        assert set(response.domain_scores) == set(
            c["domain"] for c in get_all_controls("soc2-tsc")
        )

    def test_default_framework_recorded(self):
        results = [
            _result(c["id"], "FAIL", domain=c["domain"])
            for c in get_all_controls()
        ]
        response = aggregate_results("aid", "Acme", results)
        assert response.framework_id == "nist-800-53"
        assert response.risk_level.value == "High"


class TestInherentRisk:
    def test_tier_extremes(self):
        low = {"data_sensitivity": "low", "business_criticality": "low", "access_scope": "low"}
        high = {"data_sensitivity": "high", "business_criticality": "high", "access_scope": "high"}
        assert compute_inherent_risk(low)["tier"] == "Low"        # 3 points
        assert compute_inherent_risk(high)["tier"] == "Critical"  # 9 points

    def test_tier_middle_bands(self):
        assert compute_inherent_risk({
            "data_sensitivity": "moderate",
            "business_criticality": "moderate",
            "access_scope": "low",
        })["tier"] == "Moderate"  # 5 points
        assert compute_inherent_risk({
            "data_sensitivity": "high",
            "business_criticality": "moderate",
            "access_scope": "low",
        })["tier"] == "High"  # 6 points

    def test_unknown_values_default_to_low(self):
        assert compute_inherent_risk({})["points"] == 3


class TestResidualRisk:
    def test_critical_vendor_escalates(self):
        # Even a well-scoring vendor stays elevated when inherent risk is Critical
        assert compute_residual_risk("Critical", "Low") == "Medium"
        assert compute_residual_risk("Critical", "High") == "Critical"

    def test_low_stakes_vendor_de_escalates(self):
        assert compute_residual_risk("Low", "High") == "Medium"
        assert compute_residual_risk("Low", "Medium") == "Low"

    def test_unknown_tier_falls_back_to_moderate_row(self):
        assert compute_residual_risk("Bogus", "High") == "High"
