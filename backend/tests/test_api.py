"""HTTP API tests via TestClient — isolated storage, no Qdrant, no LLM.

Covers the five product-feature endpoints (frameworks, overrides, diff,
risk profile, follow-up guardrails) plus detail enrichment.
"""

from storage.local_store import get_assessment, save_assessment
from tests.conftest import VALID_FRAMEWORK_DEF, make_control_result


def seed_assessment(aid: str, scores: dict[str, str], **extra) -> None:
    save_assessment(aid, {
        "vendor_name": "TestVendor",
        "status": "completed",
        "overall_score": 50,
        "risk_level": "Medium",
        "framework_id": "soc2-tsc",
        "domain_scores": {},
        "control_results": [
            make_control_result(cid, s, confidence=0.3 if cid == "GR-001" else 0.9)
            for cid, s in scores.items()
        ],
        **extra,
    })


class TestFrameworkEndpoints:
    def test_list_includes_builtins(self, client):
        ids = {f["id"] for f in client.get("/api/frameworks").json()["frameworks"]}
        assert {"nist-800-53", "soc2-tsc"} <= ids

    def test_controls_for_framework(self, client):
        r = client.get("/api/controls", params={"framework_id": "soc2-tsc"})
        assert r.status_code == 200
        assert len(r.json()["controls"]) == 10

    def test_unknown_framework_404(self, client):
        assert client.get("/api/controls", params={"framework_id": "nope"}).status_code == 404

    def test_save_use_delete_custom(self, client):
        assert client.post("/api/frameworks", json=VALID_FRAMEWORK_DEF).status_code == 200
        r = client.get("/api/controls", params={"framework_id": "test-questionnaire"})
        assert r.status_code == 200 and r.json()["controls"][0]["id"] == "TQ-001"
        assert client.delete("/api/frameworks/test-questionnaire").status_code == 200
        assert client.get(
            "/api/controls", params={"framework_id": "test-questionnaire"}
        ).status_code == 404

    def test_duplicate_control_ids_rejected(self, client):
        bad = {**VALID_FRAMEWORK_DEF, "id": "dupes",
               "controls": [VALID_FRAMEWORK_DEF["controls"][0]] * 2}
        assert client.post("/api/frameworks", json=bad).status_code == 422

    def test_builtin_shadow_rejected(self, client):
        bad = {**VALID_FRAMEWORK_DEF, "id": "nist-800-53"}
        assert client.post("/api/frameworks", json=bad).status_code == 409

    def test_builtin_delete_rejected(self, client):
        assert client.delete("/api/frameworks/soc2-tsc").status_code == 403

    def test_extract_rejects_tiny_document(self, client):
        r = client.post("/api/frameworks/extract",
                        files={"file": ("t.txt", b"too short", "text/plain")})
        assert r.status_code == 502
        assert "too short" in r.json()["detail"]


class TestDetailEnrichment:
    def test_needs_review_and_queue(self, client):
        # GR-001 FAIL @ conf 0.3 (low conf → queued), GR-002 PASS @ 0.9
        # (settled → not queued), AC-001 PARTIAL @ 0.9 (inconclusive →
        # queued), AC-002 NO_EVIDENCE @ 0.9 (unverified → queued)
        seed_assessment("a1", {"GR-001": "FAIL", "GR-002": "PASS",
                               "AC-001": "PARTIAL", "AC-002": "NO_EVIDENCE"})
        d = client.get("/api/assessments/a1").json()
        by_id = {c["control_id"]: c for c in d["control_results"]}
        assert by_id["GR-001"]["needs_review"] is True    # confidence 0.3
        assert by_id["GR-002"]["needs_review"] is False   # confidence 0.9
        # review_queue = needs analyst JUDGMENT (same rule as frontend
        # lib/reviewQueue): unoverridden NO_EVIDENCE/PARTIAL/low-confidence
        assert set(d["review_queue"]) == {"GR-001", "AC-001", "AC-002"}
        assert "evidence_freshness" in d

    def test_override_removes_from_review_queue(self, client):
        seed_assessment("a1b", {"GR-001": "NO_EVIDENCE"})
        assert client.get("/api/assessments/a1b").json()["review_queue"] == ["GR-001"]
        client.patch("/api/assessments/a1b/controls/GR-001/override",
                     json={"score": "PASS", "comment": "verified"})
        assert client.get("/api/assessments/a1b").json()["review_queue"] == []

    def test_missing_assessment_404(self, client):
        assert client.get("/api/assessments/ghost").status_code == 404


class TestOverride:
    def test_override_recomputes_and_keeps_audit_trail(self, client):
        seed_assessment("a2", {"GR-001": "FAIL", "GR-002": "PARTIAL", "AC-001": "NO_EVIDENCE"})
        r = client.patch("/api/assessments/a2/controls/GR-001/override",
                         json={"score": "PASS", "comment": "verified out-of-band"})
        assert r.status_code == 200
        # v3 evidence-weighted headline: PASS(1) + PARTIAL(0.5) over all 10
        # framework controls (NO_EVIDENCE + unevaluated count as 0) → 15
        assert r.json()["overall_score"] == 15

        stored = get_assessment("a2")
        c = next(x for x in stored["control_results"] if x["control_id"] == "GR-001")
        assert c["analyst_score"] == "PASS"
        assert c["score"] == "FAIL"                 # AI verdict preserved
        assert c["analyst_comment"] == "verified out-of-band"

    def test_clear_override(self, client):
        seed_assessment("a3", {"GR-001": "FAIL"})
        client.patch("/api/assessments/a3/controls/GR-001/override",
                     json={"score": "PASS"})
        r = client.patch("/api/assessments/a3/controls/GR-001/override",
                         json={"score": None})
        assert r.status_code == 200
        c = get_assessment("a3")["control_results"][0]
        assert c["analyst_score"] is None

    def test_unknown_control_404(self, client):
        seed_assessment("a4", {"GR-001": "PASS"})
        r = client.patch("/api/assessments/a4/controls/NOPE-1/override",
                         json={"score": "PASS"})
        assert r.status_code == 404


class TestDiff:
    def test_directions_and_summary(self, client):
        seed_assessment("old", {"GR-001": "FAIL", "GR-002": "PARTIAL", "AC-001": "NO_EVIDENCE"})
        seed_assessment("new", {"GR-001": "PASS", "GR-002": "PARTIAL", "AC-001": "FAIL"})
        diff = client.get("/api/assessments/old/diff/new").json()
        dirs = {c["control_id"]: c["direction"] for c in diff["controls"]}
        assert dirs == {
            "GR-001": "improved",
            "GR-002": "unchanged",
            "AC-001": "changed",   # NO_EVIDENCE→FAIL: same value, different label
        }
        assert diff["summary"]["improved"] == 1
        assert diff["framework_mismatch"] is False

    def test_missing_side_404(self, client):
        seed_assessment("only", {"GR-001": "PASS"})
        assert client.get("/api/assessments/only/diff/ghost").status_code == 404


class TestRiskProfile:
    def test_profile_computes_inherent_and_residual(self, client):
        seed_assessment("a5", {"GR-001": "PASS"})
        r = client.put("/api/assessments/a5/risk-profile", json={
            "data_sensitivity": "high",
            "business_criticality": "high",
            "access_scope": "high",
        })
        assert r.status_code == 200
        assert r.json()["inherent_risk"]["tier"] == "Critical"
        # Enrichment on subsequent reads
        d = client.get("/api/assessments/a5").json()
        assert d["inherent_risk"]["tier"] == "Critical"
        assert d["residual_risk"] in {"Medium", "High", "Critical"}

    def test_invalid_level_rejected(self, client):
        seed_assessment("a6", {"GR-001": "PASS"})
        r = client.put("/api/assessments/a6/risk-profile", json={
            "data_sensitivity": "extreme",
            "business_criticality": "high",
            "access_scope": "high",
        })
        assert r.status_code == 422


class TestCsvExport:
    def test_csv_contains_effective_scores_and_override(self, client):
        seed_assessment("csv1", {"GR-001": "FAIL", "GR-002": "PASS"})
        # analyst overrides GR-001 → CSV must show effective PASS + audit columns
        client.patch("/api/assessments/csv1/controls/GR-001/override",
                     json={"score": "PASS", "comment": "verified on call"})
        r = client.get("/api/assessments/csv1/export.csv")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        assert 'attachment; filename="vendorshield-' in r.headers["content-disposition"]
        lines = r.text.strip().splitlines()
        assert lines[0].startswith("control_id,domain,title,effective_score,ai_score")
        gr1 = next(l for l in lines if l.startswith("GR-001"))
        assert ",PASS,FAIL,PASS," in gr1          # effective, ai, analyst
        assert "verified on call" in gr1

    def test_csv_missing_assessment_404(self, client):
        assert client.get("/api/assessments/ghost/export.csv").status_code == 404

    def test_pdf_report_download(self, client):
        seed_assessment("pdf1", {"GR-001": "PASS", "GR-002": "NO_EVIDENCE"})
        r = client.get("/api/assessments/pdf1/report.pdf")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/pdf")
        assert 'attachment; filename="vendorshield-' in r.headers["content-disposition"]
        assert r.content.startswith(b"%PDF")

    def test_pdf_missing_assessment_404(self, client):
        assert client.get("/api/assessments/ghost/report.pdf").status_code == 404


class TestScannedPdfRejection:
    def _blank_pdf(self, pages: int = 2) -> bytes:
        from io import BytesIO
        from reportlab.pdfgen import canvas
        buf = BytesIO()
        c = canvas.Canvas(buf)
        for _ in range(pages):
            c.showPage()  # image-less, text-less page — like a scan
        c.save()
        return buf.getvalue()

    def test_upload_rejects_scanned_pdf_with_clear_error(self, client):
        r = client.post(
            "/api/documents/upload",
            files={"file": ("scan.pdf", self._blank_pdf(), "application/pdf")},
            data={"assessment_id": "scan-test", "vendor_name": "X"},
        )
        assert r.status_code == 422
        assert "scanned" in r.json()["detail"].lower()
        assert "OCR" in r.json()["detail"]


class TestFollowUps:
    def test_blocked_until_completed(self, client):
        save_assessment("draft1", {"vendor_name": "X", "status": "draft", "control_results": []})
        assert client.post("/api/assessments/draft1/follow-up-questions").status_code == 400

    def test_get_before_generate_404(self, client):
        seed_assessment("a7", {"GR-001": "FAIL"})
        assert client.get("/api/assessments/a7/follow-up-questions").status_code == 404
