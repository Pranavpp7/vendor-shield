"""Demo seed data — three fictional vendors with contrasting risk stories.

Creates deterministic, LLM-free demo assessments so the app demos warm:

    acme-cloud-demo      Strong SaaS vendor, NIST framework, low risk,
                         TWO runs (lights up the diff panel + sparkline)
    shadowpix-demo       Weak startup, SOC 2 framework, high risk,
                         one analyst override + low-confidence controls
                         (lights up the Review tab + agreement stat)
    meridian-pay-demo    Mid-tier payments vendor, NIST, medium risk,
                         Critical inherent-risk profile (residual risk demo)

Also ingests a small security document per vendor into Qdrant (local
embeddings, no API cost) so the Chat tab and retrieval work.  Qdrant
being down is non-fatal — records still seed.

Usage (from backend/):
    uv run python seed.py           # create/refresh the demo vendors
    uv run python seed.py --clean   # remove them
"""

import sys
from datetime import datetime, timedelta, timezone

from models.controls import get_all_controls
from storage.local_store import (
    delete_assessment,
    init_db,
    save_assessment,
    save_document_meta,
    generate_id,
)

# ── Score patterns per vendor ────────────────────────────────────────────────
# control index → score; anything unlisted falls back to the default.

REASONING = {
    "PASS": "The documentation directly and specifically addresses this control with named mechanisms and scope.",
    "PARTIAL": "The documentation mentions this area but lacks specifics on scope, frequency, or enforcement.",
    "FAIL": "The documentation indicates practices that do not meet this control's standard.",
    "NO_EVIDENCE": "No relevant statements about this control were found in the provided documents.",
}

GAP = {
    "PASS": None,
    "PARTIAL": "Request specifics: named tooling, defined frequency, and enforcement scope.",
    "FAIL": "This practice must be remediated before the vendor meets the control standard.",
    "NO_EVIDENCE": "Ask the vendor to provide documentation covering this control.",
}

EVIDENCE = {
    "PASS": "See the vendor security overview — the relevant section names the mechanism and its scope explicitly.",
    "PARTIAL": "A brief mention appears in the security overview, without implementation detail.",
}


def _iso(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def build_controls(framework_id: str, pattern: dict[int, str], default: str,
                   confidences: dict[int, float] | None = None) -> list[dict]:
    controls = get_all_controls(framework_id)
    results = []
    for i, c in enumerate(controls):
        score = pattern.get(i, default)
        confidence = (confidences or {}).get(i, 0.9 if score == "PASS" else 0.7)
        results.append({
            "control_id": c["id"],
            "score": score,
            "confidence": confidence,
            "evidence_quote": EVIDENCE.get(score),
            "evidence_chunk": 1 if score in EVIDENCE else None,
            "reasoning": REASONING[score],
            "gap": GAP[score],
            "domain": c["domain"],
            "title": c["title"],
            "citations": [],
            "analyst_score": None,
            "analyst_comment": None,
            "overridden_by": None,
            "overridden_at": None,
        })
    return results


def compute(framework_id: str, results: list[dict]) -> dict:
    from models.controls import calculate_scores
    return calculate_scores(results, framework_id)


SEED_DOC = {
    "acme-cloud-demo": (
        "AcmeCloud Security Overview\n\n"
        "All customer data at rest is encrypted with AES-256; keys live in a "
        "dedicated KMS with annual rotation. All traffic uses TLS 1.3 with "
        "mTLS between internal services. MFA with hardware keys is mandatory "
        "for every employee. Quarterly access reviews are logged and audited. "
        "An independent firm performs annual penetration tests; findings are "
        "tracked to closure within 30 days. Our 24/7 SOC monitors a central "
        "SIEM with 13-month log retention."
    ),
    "shadowpix-demo": (
        "ShadowPix Trust FAQ\n\n"
        "We take security seriously. Passwords are required for all accounts. "
        "Our team reviews systems periodically and applies updates when "
        "available. Customer files are stored on reputable cloud providers."
    ),
    "meridian-pay-demo": (
        "MeridianPay Security Whitepaper\n\n"
        "Cardholder data is encrypted at rest (AES-256) and in transit "
        "(TLS 1.2+). MFA is enforced for administrative access. We maintain "
        "an incident response plan reviewed annually and notify customers of "
        "confirmed breaches within 72 hours. Vulnerability scans run monthly; "
        "we are working to formalize our data retention schedule and "
        "centralized log correlation."
    ),
}


def seed() -> None:
    init_db()
    now = datetime.now(timezone.utc)

    # ── 1. AcmeCloud — strong vendor, NIST, two runs (improvement story) ────
    strong = build_controls("nist-800-53", {3: "PARTIAL", 13: "PARTIAL"}, "PASS")
    strong_scores = compute("nist-800-53", strong)
    save_assessment("acme-cloud-demo", {
        "vendor_name": "AcmeCloud (Demo)",
        "status": "completed",
        "framework_id": "nist-800-53",
        "control_results": strong,
        "overall_score": strong_scores["overall_score"],
        "risk_level": strong_scores["risk_level"],
        "domain_scores": strong_scores["domain_scores"],
        "gaps_summary": "## Gaps Summary\n\nMinor gaps only — see PARTIAL controls.",
        "created_at": _iso(30),
        "risk_profile": {"data_sensitivity": "moderate", "business_criticality": "high", "access_scope": "moderate"},
        "run_history": [
            {"run_id": "seed0001", "score": 72, "risk_level": "Low",
             "pass_count": 13, "partial_count": 3, "fail_count": 2, "no_evidence_count": 2,
             "ran_at": _iso(30)},
            {"run_id": "seed0002", "score": strong_scores["overall_score"],
             "risk_level": strong_scores["risk_level"],
             "pass_count": 18, "partial_count": 2, "fail_count": 0, "no_evidence_count": 0,
             "ran_at": _iso(2)},
        ],
        "run_metrics": {"llm_calls": 21, "prompt_tokens": 38000, "completion_tokens": 3900,
                        "estimated_cost_usd": 0.006, "duration_seconds": 84},
    })
    # An earlier, weaker run of the same vendor for the diff panel
    earlier = build_controls(
        "nist-800-53",
        {3: "PARTIAL", 13: "PARTIAL", 5: "NO_EVIDENCE", 9: "NO_EVIDENCE", 11: "FAIL", 17: "FAIL", 7: "PARTIAL"},
        "PASS",
    )
    earlier_scores = compute("nist-800-53", earlier)
    save_assessment("acme-cloud-demo-r1", {
        "vendor_name": "AcmeCloud (Demo)",
        "status": "completed",
        "framework_id": "nist-800-53",
        "control_results": earlier,
        "overall_score": earlier_scores["overall_score"],
        "risk_level": earlier_scores["risk_level"],
        "domain_scores": earlier_scores["domain_scores"],
        "gaps_summary": "## Gaps Summary\n\nSeveral controls lacked evidence in the first document set.",
        "created_at": _iso(31),
    })

    # ── 2. ShadowPix — weak vendor, SOC 2, override + review queue ──────────
    weak = build_controls(
        "soc2-tsc",
        {0: "PARTIAL", 2: "PARTIAL", 4: "FAIL", 6: "NO_EVIDENCE"},
        "NO_EVIDENCE",
        confidences={1: 0.3, 3: 0.35, 6: 0.25},  # low-confidence → review queue
    )
    # One analyst override with audit trail: AI said NO_EVIDENCE, human
    # confirmed backups exist after a call with the vendor.
    weak[7]["analyst_score"] = "PARTIAL"
    weak[7]["analyst_comment"] = "Vendor demonstrated nightly backups on a call; recovery testing still unproven."
    weak[7]["overridden_by"] = ""
    weak[7]["overridden_at"] = _iso(1)
    weak_scores = compute("soc2-tsc", weak)
    save_assessment("shadowpix-demo", {
        "vendor_name": "ShadowPix (Demo)",
        "status": "completed",
        "framework_id": "soc2-tsc",
        "control_results": weak,
        "overall_score": weak_scores["overall_score"],
        "risk_level": weak_scores["risk_level"],
        "domain_scores": weak_scores["domain_scores"],
        "gaps_summary": "## Gaps Summary\n\nMost controls lack evidence — request their security policy suite.",
        "created_at": _iso(5),
        "risk_profile": {"data_sensitivity": "high", "business_criticality": "low", "access_scope": "moderate"},
        "run_metrics": {"llm_calls": 11, "prompt_tokens": 16500, "completion_tokens": 1900,
                        "estimated_cost_usd": 0.003, "duration_seconds": 47},
        "follow_up_questions": {
            "questions": [
                {"control_id": weak[6]["control_id"], "domain": weak[6]["domain"],
                 "question": "Can you share your incident response plan, including severity levels and customer notification timeframes?",
                 "rationale": "No incident response documentation was found."},
                {"control_id": weak[4]["control_id"], "domain": weak[4]["domain"],
                 "question": "Please provide evidence of encryption at rest and in transit, including algorithms and TLS versions.",
                 "rationale": "The FAQ does not describe encryption anywhere."},
            ],
            "generated_at": _iso(1),
        },
    })

    # ── 3. MeridianPay — mid-tier vendor, Critical inherent risk ────────────
    mid = build_controls(
        "nist-800-53",
        {0: "PASS", 5: "PASS", 6: "PASS", 8: "PARTIAL", 9: "NO_EVIDENCE",
         10: "PASS", 13: "PASS", 15: "PASS", 16: "PARTIAL", 18: "NO_EVIDENCE"},
        "PARTIAL",
    )
    mid_scores = compute("nist-800-53", mid)
    save_assessment("meridian-pay-demo", {
        "vendor_name": "MeridianPay (Demo)",
        "status": "completed",
        "framework_id": "nist-800-53",
        "control_results": mid,
        "overall_score": mid_scores["overall_score"],
        "risk_level": mid_scores["risk_level"],
        "domain_scores": mid_scores["domain_scores"],
        "gaps_summary": "## Gaps Summary\n\nRetention schedule and log correlation are the notable gaps.",
        "created_at": _iso(12),
        "risk_profile": {"data_sensitivity": "high", "business_criticality": "high", "access_scope": "high"},
        "run_metrics": {"llm_calls": 20, "prompt_tokens": 36000, "completion_tokens": 3600,
                        "estimated_cost_usd": 0.0055, "duration_seconds": 78},
    })

    # ── Documents: metadata always; vectors only if Qdrant is up ────────────
    for aid, text in SEED_DOC.items():
        doc_name = f"{aid.replace('-demo', '')}-security-overview.txt"
        chunks_created = 0
        try:
            from services.chunking import split_text
            from services.embedding import embed_chunks
            from storage.qdrant_store import add_chunks, create_collection, delete_collection

            chunks = split_text(text)
            vectors = embed_chunks(chunks)
            try:
                delete_collection(aid)
            except Exception:
                pass
            create_collection(aid)
            add_chunks(
                assessment_id=aid,
                chunks=chunks,
                vectors=vectors,
                document_name=doc_name,
            )
            chunks_created = len(chunks)
            print(f"  vectors: {aid} ({chunks_created} chunks)")
        except Exception as e:
            print(f"  vectors skipped for {aid} (Qdrant/embedding unavailable): {e}")

        save_document_meta(generate_id(), {
            "assessment_id": aid,
            "file_name": doc_name,
            "source_type": "txt",
            "chunks_created": chunks_created,
            "created_at": _iso(400 if aid == "shadowpix-demo" else 5),  # stale-evidence demo
        })

    print("Seeded 4 demo assessments (3 vendors, one with 2 runs).")


def clean() -> None:
    init_db()
    from storage.local_store import list_documents, delete_document_meta
    for aid in ("acme-cloud-demo", "acme-cloud-demo-r1", "shadowpix-demo", "meridian-pay-demo"):
        for doc in list_documents(assessment_id=aid):
            delete_document_meta(doc["id"])
        try:
            from storage.qdrant_store import delete_collection
            delete_collection(aid)
        except Exception:
            pass
        delete_assessment(aid)
    print("Removed demo vendors.")


if __name__ == "__main__":
    if "--clean" in sys.argv:
        clean()
    else:
        seed()
