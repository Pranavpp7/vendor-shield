"""PDF report generation — renders override-aware, framework-aware reports."""

from services.email_service import generate_pdf_report
from tests.conftest import make_control_result


def _assessment(**extra) -> dict:
    return {
        "vendor_name": "PDF Test Vendor",
        "overall_score": 55,
        "risk_level": "Medium",
        "framework_id": "soc2-tsc",
        "domain_scores": {"Governance & Risk": 50, "Access Control": 60},
        "control_results": [
            make_control_result("GR-001", "FAIL", analyst_score="PASS",
                                analyst_comment="verified", overridden_at="2026-07-01T00:00:00Z"),
            make_control_result("GR-002", "PARTIAL"),
            make_control_result("AC-001", "NO_EVIDENCE", domain="Access Control"),
        ],
        "created_at": "2026-07-03T12:00:00+00:00",
        **extra,
    }


def test_pdf_renders_with_overrides_and_followups(tmp_custom_frameworks):
    pdf = generate_pdf_report(_assessment(
        risk_profile={"data_sensitivity": "high", "business_criticality": "high", "access_scope": "high"},
        follow_up_questions={"questions": [
            {"control_id": "AC-001", "domain": "Access Control",
             "question": "Please share your access control policy.", "rationale": "No evidence found."},
        ], "generated_at": "2026-07-02T00:00:00Z"},
    ))
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 3000  # a real multi-section report, not an empty shell


def test_pdf_renders_minimal_legacy_record(tmp_custom_frameworks):
    # Legacy records: no framework_id, no profile, no follow-ups
    record = _assessment()
    del record["framework_id"]
    pdf = generate_pdf_report(record)
    assert pdf.startswith(b"%PDF")
