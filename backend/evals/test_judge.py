"""DeepEval judge-tier evals — rubric-grade the SUBJECTIVE outputs.

The golden gate (run_evals.py) checks the objective layer: score bands,
false-PASS, verbatim citations.  This suite judges what has no single
right answer — the quality of the LLM's written reasoning — using
DeepEval's G-Eval metric with the project's own LLM as the judge
(via services/llm, so provider failover and metering apply to judge
calls too).

It reads the artifact written by the golden gate rather than re-running
the pipeline, so the only LLM spend here is the judge calls themselves.

Requires:
    - the eval dependency group:   uv sync --group eval
    - a fresh artifact:            uv run python evals/run_evals.py
    - an LLM key configured (OPENROUTER_API_KEY or FALLBACK_API_KEY)

Run (deliberately OUTSIDE default pytest discovery — testpaths=["tests"]):
    uv run --group eval pytest evals/test_judge.py -q

Cost: ~1-2 judge calls per sampled result, max ~14 samples (≈ $0.02).
"""

import json
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

deepeval = pytest.importorskip(
    "deepeval", reason="eval group not installed (uv sync --group eval)"
)
from deepeval import assert_test  # noqa: E402
from deepeval.metrics import GEval  # noqa: E402
from deepeval.models import DeepEvalBaseLLM  # noqa: E402
from deepeval.test_case import LLMTestCase, LLMTestCaseParams  # noqa: E402

ARTIFACT = Path(__file__).resolve().parent / "last_run_results.json"

# Cap judge spend: at most this many sampled results per test class.
MAX_SCORED_SAMPLES = 8
MAX_NO_EVIDENCE_SAMPLES = 6

# The honest system-failure fallback texts are not LLM reasoning — never
# judge them for quality (they already mean "this call failed").
_SYSTEM_FAILURE_MARKER = "This is a system issue"


def _llm_available() -> bool:
    from config import get_settings

    s = get_settings()
    return bool(s.openrouter_api_key or s.fallback_api_key)


if not ARTIFACT.exists():
    pytest.skip(
        "no eval artifact — run `uv run python evals/run_evals.py` first",
        allow_module_level=True,
    )
if not _llm_available():
    pytest.skip("no LLM key configured for the judge", allow_module_level=True)

_artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
_documents: dict[str, str] = _artifact["documents"]
_results: list[dict] = _artifact["results"]


# ── Judge model: route DeepEval through services/llm ─────────────────────────


_FENCE = re.compile(r"^```[a-zA-Z]*\s*|```\s*$")


def _extract_json(raw: str) -> str:
    cleaned = _FENCE.sub("", raw.strip()).strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    return match.group(0) if match else cleaned


class VendorShieldJudge(DeepEvalBaseLLM):
    """DeepEval judge backed by the app's own LLM module (failover included)."""

    def __init__(self):
        from config import get_settings

        self._model = get_settings().openrouter_model

    def load_model(self):
        return None

    def generate(self, prompt: str, schema=None):
        from services.llm import complete

        text = complete(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1024,
            json_mode=schema is not None,
        )
        if schema is None:
            return text
        return schema.model_validate_json(_extract_json(text))

    async def a_generate(self, prompt: str, schema=None):
        from services.llm import acomplete

        text = await acomplete(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1024,
            json_mode=schema is not None,
        )
        if schema is None:
            return text
        return schema.model_validate_json(_extract_json(text))

    def get_model_name(self):
        return f"vendorshield-judge ({self._model})"


@pytest.fixture(scope="module")
def judge() -> VendorShieldJudge:
    return VendorShieldJudge()


# ── Sampling (deterministic: sorted, capped) ─────────────────────────────────


def _sample(records: list[dict], cap: int) -> list[dict]:
    return sorted(records, key=lambda r: (r["case_id"], r["control_id"]))[:cap]


_scored = _sample(
    [
        r for r in _results
        if r["got"] in ("PASS", "PARTIAL", "FAIL")
        and r["reasoning"]
        and _SYSTEM_FAILURE_MARKER not in r["reasoning"]
    ],
    MAX_SCORED_SAMPLES,
)

_no_evidence = _sample(
    [
        r for r in _results
        if r["got"] == "NO_EVIDENCE"
        and r["reasoning"]
        and _SYSTEM_FAILURE_MARKER not in r["reasoning"]
    ],
    MAX_NO_EVIDENCE_SAMPLES,
)


def _rid(r: dict) -> str:
    return f"{r['case_id']}/{r['control_id']}"


# ── Judge tests ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("record", _scored, ids=_rid)
def test_scored_reasoning_is_grounded(record: dict, judge: VendorShieldJudge):
    """PASS/PARTIAL/FAIL reasoning must be grounded in the vendor document."""
    metric = GEval(
        name="Grounded reasoning",
        criteria=(
            "The actual output is an auditor's reasoning for a verdict on one "
            "vendor-security control.  Judge whether it is grounded in the "
            "context (the vendor's own document): every factual claim about "
            "the vendor must be supported by the context; it should cite "
            "specifics (tools, cadences, standards, timeframes) from the "
            "context rather than generic filler; and it must not attribute "
            "certifications, tools, or practices to the vendor that the "
            "context does not contain."
        ),
        evaluation_params=[
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.CONTEXT,
        ],
        threshold=0.6,
        model=judge,
        async_mode=False,
    )
    assert_test(
        LLMTestCase(
            input=(
                f"{record['control_id']} {record['control_title']} — "
                f"verdict {record['got']}"
            ),
            actual_output=record["reasoning"],
            context=[_documents[record["case_id"]]],
        ),
        [metric],
    )


@pytest.mark.parametrize("record", _no_evidence, ids=_rid)
def test_no_evidence_reasoning_is_honest(record: dict, judge: VendorShieldJudge):
    """NO_EVIDENCE reasoning must describe the gap without asserting failure."""
    metric = GEval(
        name="Honest NO_EVIDENCE reasoning",
        criteria=(
            "The actual output explains why a vendor-security control was "
            "marked NO_EVIDENCE (nothing relevant found in the vendor's "
            "documents).  Judge whether it: states what was searched for or "
            "what kind of evidence is missing; does NOT assert that the "
            "vendor lacks or fails the practice (absence of evidence is not "
            "failure); and does not fabricate evidence or quote text that "
            "was supposedly found."
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        threshold=0.6,
        model=judge,
        async_mode=False,
    )
    assert_test(
        LLMTestCase(
            input=(
                f"{record['control_id']} {record['control_title']} — "
                "verdict NO_EVIDENCE"
            ),
            actual_output=record["reasoning"],
        ),
        [metric],
    )
