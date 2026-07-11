"""One-time (idempotent) score recompute over stored assessments.

Scoring semantics have evolved (v1 → v2 → v3, see calculate_scores in
models/controls.py) but stored records keep the numbers computed at run
time.  This recalculates overall/verified/coverage/domain scores and
risk level for every stored assessment from its control_results — pure
math, no LLM calls, overrides respected.

Usage (from backend/):
    uv run python recompute_scores.py
"""

from models.controls import calculate_scores, resolve_framework_id
from storage.local_store import init_db, list_assessments, update_assessment


def main() -> None:
    init_db()
    updated = skipped = 0
    for record in list_assessments():
        controls = record.get("control_results") or []
        if not controls:
            skipped += 1
            continue
        try:
            framework_id = resolve_framework_id(record.get("framework_id", ""))
        except KeyError:
            framework_id = resolve_framework_id("")  # deleted custom framework
        scores = calculate_scores(controls, framework_id)
        changed = (
            record.get("overall_score") != scores["overall_score"]
            or record.get("domain_scores") != scores["domain_scores"]
            or record.get("risk_level") != scores["risk_level"]
        )
        update_assessment(record["id"], {
            "overall_score": scores["overall_score"],
            "risk_level": scores["risk_level"],
            "domain_scores": scores["domain_scores"],
            "coverage": scores["coverage"],
            "verified_score": scores["verified_score"],
        })
        updated += 1
        marker = "*" if changed else " "
        print(
            f" {marker} {record['id'][:36]:38} {record.get('vendor_name', '')[:20]:22} "
            f"score={scores['overall_score']:3} verified={scores['verified_score']:3} "
            f"cov={scores['coverage']:3}% risk={scores['risk_level']}"
        )
    print(f"\nRecomputed {updated} assessment(s), skipped {skipped} without results. (* = values changed)")


if __name__ == "__main__":
    main()
