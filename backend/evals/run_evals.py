"""Golden-dataset evals — regression-test the scoring pipeline.

For each case in golden_vendors.json:
    1. Ingest the fictional vendor document into a throwaway assessment
       (local embeddings + Qdrant — real retrieval, real chunking)
    2. Run the real evaluation pipeline (real LLM calls)
    3. Compare each control's score against the expected score band

THREE gates — ALL must pass for exit code 0:

    agreement    Overall score-band agreement >= --threshold (default 80%).
    false-PASS   Count of PASS verdicts where PASS is not in the expected
                 band must be <= --max-false-pass (default 0).  A false
                 PASS greenlights a risky vendor — the one error class
                 this product must never make — so it fails the gate
                 regardless of how good overall agreement looks.
    faithfulness Citation faithfulness >= --min-faithfulness (default 90%).
                 Every evidence_quote must appear (whitespace/quote-
                 normalized; "..." splits into segments) in the case
                 document.  A quote that doesn't is hallucinated evidence.

Every run is also:
    - persisted to SQLite (eval_runs table), stamped with the model id and
      a hash of the scoring prompt so regressions are attributable to a
      specific model or prompt change
    - dumped in full to evals/last_run_results.json — consumed by the
      DeepEval judge suite (evals/test_judge.py) and uploaded as an
      artifact by the nightly workflow (.github/workflows/evals.yml)

NOT run in per-PR CI (needs Qdrant + an OpenRouter key); the nightly
workflow runs it on a schedule.  Run it manually before and after touching
get_scoring_prompt(), the model, retrieval_top_k, or chunking:

    uv run python evals/run_evals.py
    uv run python evals/run_evals.py --threshold 70

Cost: ~50 LLM calls (~$0.02 with the default model).
"""

import argparse
import asyncio
import hashlib
import inspect
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GOLDEN = Path(__file__).resolve().parent / "golden_vendors.json"
ARTIFACT = Path(__file__).resolve().parent / "last_run_results.json"


# ── Pure helpers (unit-tested in tests/test_evals_gate.py) ───────────────────


def _normalize(text: str) -> str:
    """Lowercase, straighten curly quotes/dashes, collapse whitespace."""
    text = text.lower()
    for fancy, plain in (
        ("“", '"'), ("”", '"'),
        ("‘", "'"), ("’", "'"),
        ("–", "-"), ("—", "-"),
    ):
        text = text.replace(fancy, plain)
    return " ".join(text.split())


_ELLIPSIS = re.compile(r"\[\s*(?:\.\.\.|…)\s*\]|\.\.\.|…")


def quote_is_faithful(quote: str, document: str) -> bool:
    """True when the quote appears verbatim in the document.

    Comparison is whitespace/quote-normalized.  Ellipses ("...", "…",
    "[...]") split the quote into segments that must each appear; segments
    shorter than 12 characters are too generic to check and are skipped.
    """
    doc = _normalize(document)
    segments = [s.strip(" \"'") for s in _ELLIPSIS.split(_normalize(quote))]
    segments = [s for s in segments if len(s) >= 12]
    if not segments:
        segments = [_normalize(quote).strip(" \"'")]
    return all(s in doc for s in segments)


def is_false_pass(got: str, expected: list[str]) -> bool:
    """The dangerous miss: scored PASS when PASS is not an accepted band."""
    return got == "PASS" and "PASS" not in expected


def scoring_prompt_hash() -> str:
    """Fingerprint of the scoring prompt builder, for regression attribution."""
    from models.controls import get_scoring_prompt

    source = inspect.getsource(get_scoring_prompt)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]


# ── Pipeline plumbing ────────────────────────────────────────────────────────


def ingest(assessment_id: str, name: str, text: str) -> None:
    from services.chunking import split_text
    from services.embedding import embed_chunks
    from storage.qdrant_store import add_chunks, create_collection, delete_collection

    try:
        delete_collection(assessment_id)
    except Exception:
        pass
    chunks = split_text(text)
    create_collection(assessment_id)
    add_chunks(
        assessment_id=assessment_id,
        chunks=chunks,
        vectors=embed_chunks(chunks),
        document_name=name,
    )


def cleanup(assessment_id: str) -> None:
    from storage.qdrant_store import delete_collection

    try:
        delete_collection(assessment_id)
    except Exception:
        pass


async def run_case(case: dict, framework_id: str) -> list[dict]:
    """Run one golden case; return one record dict per expected control."""
    from services.evaluation import evaluate_all_controls

    aid = f"zz-{case['id']}"
    ingest(aid, f"{case['id']}.txt", case["document"])
    try:
        results = await evaluate_all_controls(aid, framework_id=framework_id)
    finally:
        cleanup(aid)

    records: list[dict] = []
    for r in results:
        expected = case["expected"].get(r.control_id)
        if not expected:
            continue
        got = r.score.value
        records.append({
            "case_id": case["id"],
            "case_name": case["name"],
            "control_id": r.control_id,
            "control_title": r.title,
            "got": got,
            "expected": expected,
            "agreed": got in expected,
            "false_pass": is_false_pass(got, expected),
            "confidence": r.confidence,
            "evidence_quote": r.evidence_quote,
            "faithful": (
                quote_is_faithful(r.evidence_quote, case["document"])
                if r.evidence_quote else None
            ),
            "reasoning": r.reasoning,
            "gap": r.gap,
        })
    return records


def _print_case(records: list[dict]) -> None:
    for r in records:
        flags = []
        if not r["agreed"]:
            flags.append("MISS")
        if r["false_pass"]:
            flags.append("FALSE-PASS")
        if r["faithful"] is False:
            flags.append("HALLUCINATED-QUOTE")
        marker = ",".join(flags) if flags else "ok"
        line = (
            f"  {marker:<24} {r['control_id']}: got {r['got']:<12} "
            f"expected {'/'.join(r['expected'])}"
        )
        if not r["agreed"]:
            line += f"  (conf {r['confidence']:.2f})"
        print(line)
    agreed = sum(r["agreed"] for r in records)
    total = len(records)
    print(f"  case agreement: {agreed}/{total} ({100 * agreed // max(total, 1)}%)\n")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run scoring evals against the golden dataset")
    parser.add_argument("--threshold", type=int, default=80,
                        help="Minimum overall agreement %% to pass (default 80)")
    parser.add_argument("--max-false-pass", type=int, default=0,
                        help="Maximum tolerated false-PASS verdicts (default 0)")
    parser.add_argument("--min-faithfulness", type=int, default=90,
                        help="Minimum %% of evidence quotes that must appear "
                             "verbatim in the source document (default 90)")
    args = parser.parse_args()

    from config import get_settings

    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    framework_id = golden["framework_id"]
    settings = get_settings()
    prompt_hash = scoring_prompt_hash()

    print(
        f"Running {len(golden['cases'])} eval case(s) against framework "
        f"'{framework_id}'\nmodel={settings.openrouter_model}  "
        f"prompt_hash={prompt_hash}\n"
    )
    started = time.perf_counter()

    all_records: list[dict] = []
    for case in golden["cases"]:
        print(f"— {case['name']}")
        records = await run_case(case, framework_id)
        _print_case(records)
        all_records.extend(records)

    elapsed = time.perf_counter() - started

    # ── Gate 1: overall agreement ────────────────────────────────────────────
    agreed = sum(r["agreed"] for r in all_records)
    total = len(all_records)
    rate = 100 * agreed // max(total, 1)
    agreement_ok = rate >= args.threshold

    # ── Gate 2: false-PASS (the greenlight-a-risky-vendor error) ─────────────
    false_passes = [r for r in all_records if r["false_pass"]]
    false_pass_ok = len(false_passes) <= args.max_false_pass

    # ── Gate 3: citation faithfulness ────────────────────────────────────────
    quoted = [r for r in all_records if r["evidence_quote"]]
    unfaithful = [r for r in quoted if r["faithful"] is False]
    # No quotes at all = vacuously faithful (the gate has nothing to judge;
    # the printout below flags it as suspicious instead of failing the run).
    faith_rate = (
        100 if not quoted
        else 100 * (len(quoted) - len(unfaithful)) // len(quoted)
    )
    faithfulness_ok = faith_rate >= args.min_faithfulness

    passed = agreement_ok and false_pass_ok and faithfulness_ok

    def _verdict(ok: bool) -> str:
        return "PASS" if ok else "FAIL"

    print(f"Agreement:    {agreed}/{total} ({rate}%) — "
          f"{_verdict(agreement_ok)} (threshold {args.threshold}%)")
    print(f"False-PASS:   {len(false_passes)} — "
          f"{_verdict(false_pass_ok)} (max {args.max_false_pass})")
    for r in false_passes:
        print(f"    !! {r['case_id']}/{r['control_id']}: scored PASS, "
              f"expected {'/'.join(r['expected'])}")
    if quoted:
        print(f"Faithfulness: {len(quoted) - len(unfaithful)}/{len(quoted)} "
              f"quotes verbatim ({faith_rate}%) — "
              f"{_verdict(faithfulness_ok)} (min {args.min_faithfulness}%)")
    else:
        print("Faithfulness: no evidence quotes produced — nothing to check "
              "(suspicious if the strong-vendor case ran)")
    for r in unfaithful:
        print(f"    !! {r['case_id']}/{r['control_id']}: quote not found in "
              f"document: {r['evidence_quote'][:80]!r}")
    print(f"\nOverall: {_verdict(passed)} in {elapsed:.0f}s")

    # ── Persist: SQLite history + JSON artifact for the judge suite ──────────
    run_summary = {
        "agreed": agreed,
        "total": total,
        "agreement": rate,
        "threshold": args.threshold,
        "passed": passed,
        "duration_s": round(elapsed, 1),
        "detail": {
            "model": settings.openrouter_model,
            "prompt_hash": prompt_hash,
            "framework_id": framework_id,
            "false_pass": [f"{r['case_id']}/{r['control_id']}" for r in false_passes],
            "faithfulness_pct": faith_rate,
            "quoted_results": len(quoted),
            "per_case": {
                case["id"]: {
                    "agreed": sum(r["agreed"] for r in all_records
                                  if r["case_id"] == case["id"]),
                    "total": sum(1 for r in all_records
                                 if r["case_id"] == case["id"]),
                }
                for case in golden["cases"]
            },
        },
    }
    try:
        from storage.local_store import init_db, record_eval_run

        init_db()
        record_eval_run(run_summary)
        print("Recorded run in eval_runs (SQLite).")
    except Exception as e:  # persistence must never mask the gate verdict
        print(f"WARNING: could not persist eval run: {e}")

    ARTIFACT.write_text(
        json.dumps(
            {
                **run_summary,
                "documents": {c["id"]: c["document"] for c in golden["cases"]},
                "results": all_records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote artifact: {ARTIFACT.name}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
