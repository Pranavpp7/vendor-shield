"""Golden-dataset evals — regression-test the scoring pipeline.

For each case in golden_vendors.json:
    1. Ingest the fictional vendor document into a throwaway assessment
       (local embeddings + Qdrant — real retrieval, real chunking)
    2. Run the real evaluation pipeline (real LLM calls)
    3. Compare each control's score against the expected score band
    4. Report per-control agreement and an overall agreement rate

Exit code 0 when overall agreement >= threshold (default 80%), else 1 —
so this can gate prompt/model changes.  NOT run in CI (needs Qdrant +
an OpenRouter key); run it manually before and after touching
get_scoring_prompt(), the model, retrieval_top_k, or chunking:

    uv run python evals/run_evals.py
    uv run python evals/run_evals.py --threshold 70

Cost: ~20 LLM calls (~$0.01 with the default model).
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GOLDEN = Path(__file__).resolve().parent / "golden_vendors.json"


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


async def run_case(case: dict, framework_id: str) -> tuple[int, int, list[str]]:
    from services.evaluation import evaluate_all_controls

    aid = f"zz-{case['id']}"
    ingest(aid, f"{case['id']}.txt", case["document"])
    try:
        results = await evaluate_all_controls(aid, framework_id=framework_id)
    finally:
        cleanup(aid)

    agreed, total = 0, 0
    lines: list[str] = []
    for r in results:
        expected = case["expected"].get(r.control_id)
        if not expected:
            continue
        total += 1
        got = r.score.value
        ok = got in expected
        agreed += ok
        marker = "  ok " if ok else "MISS "
        lines.append(
            f"  {marker} {r.control_id}: got {got:<12} expected {'/'.join(expected)}"
            + (f"  (conf {r.confidence:.2f})" if not ok else "")
        )
    return agreed, total, lines


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run scoring evals against the golden dataset")
    parser.add_argument("--threshold", type=int, default=80,
                        help="Minimum overall agreement %% to pass (default 80)")
    args = parser.parse_args()

    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    framework_id = golden["framework_id"]

    print(f"Running {len(golden['cases'])} eval case(s) against framework '{framework_id}'\n")
    started = time.perf_counter()

    total_agreed, total_controls = 0, 0
    for case in golden["cases"]:
        print(f"— {case['name']}")
        agreed, total, lines = await run_case(case, framework_id)
        total_agreed += agreed
        total_controls += total
        print("\n".join(lines))
        print(f"  case agreement: {agreed}/{total} ({100 * agreed // max(total, 1)}%)\n")

    elapsed = time.perf_counter() - started
    rate = 100 * total_agreed // max(total_controls, 1)
    verdict = "PASS" if rate >= args.threshold else "FAIL"
    print(
        f"Overall agreement: {total_agreed}/{total_controls} ({rate}%) — "
        f"{verdict} (threshold {args.threshold}%) in {elapsed:.0f}s"
    )
    return 0 if rate >= args.threshold else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
