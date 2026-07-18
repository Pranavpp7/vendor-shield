"""Deterministic tests for the golden-gate helpers (evals/run_evals.py).

These run in per-PR CI with no LLM and no Qdrant: they pin the pure
functions that decide the gate's verdicts (citation faithfulness,
false-PASS classification, prompt-hash attribution) and the shape of
the golden dataset — including the invariant that the prompt-injection
cases never accept PASS.
"""

import json
from pathlib import Path

from evals.run_evals import (
    GOLDEN,
    is_false_pass,
    quote_is_faithful,
    scoring_prompt_hash,
)

DOC = (
    "NimbusOps Security Overview\n\n"
    "Multi-factor authentication with hardware security keys is mandatory "
    "for all employees with no exceptions. All customer data is encrypted "
    'at rest with AES-256 and in transit with TLS 1.3 ("legacy" protocols '
    "disabled)."
)


class TestQuoteFaithfulness:
    def test_exact_substring_is_faithful(self):
        assert quote_is_faithful(
            "Multi-factor authentication with hardware security keys is mandatory",
            DOC,
        )

    def test_whitespace_and_curly_quotes_normalize(self):
        quote = "encrypted  at rest\nwith AES-256 and in transit with TLS 1.3 (“legacy” protocols disabled)"
        assert quote_is_faithful(quote, DOC)

    def test_ellipsis_splits_into_segments(self):
        quote = "Multi-factor authentication ... mandatory for all employees"
        assert quote_is_faithful(quote, DOC)

    def test_bracketed_ellipsis_also_splits(self):
        quote = "Multi-factor authentication [...] mandatory for all employees"
        assert quote_is_faithful(quote, DOC)

    def test_hallucinated_quote_is_caught(self):
        assert not quote_is_faithful(
            "We hold ISO 27001 certification since 2019", DOC
        )

    def test_one_hallucinated_segment_fails_the_whole_quote(self):
        quote = "Multi-factor authentication ... audited annually by Deloitte"
        assert not quote_is_faithful(quote, DOC)

    def test_short_segments_fall_back_to_full_quote(self):
        # Segments under 12 chars are too generic alone; the full
        # normalized quote must then appear.
        assert not quote_is_faithful("MFA on ... keys", DOC)
        assert quote_is_faithful("AES-256", DOC)  # short but present verbatim


class TestFalsePass:
    def test_pass_outside_expected_band_is_false_pass(self):
        assert is_false_pass("PASS", ["NO_EVIDENCE", "PARTIAL", "FAIL"])

    def test_pass_inside_expected_band_is_fine(self):
        assert not is_false_pass("PASS", ["PASS", "PARTIAL"])

    def test_non_pass_scores_are_never_false_pass(self):
        assert not is_false_pass("FAIL", ["NO_EVIDENCE"])
        assert not is_false_pass("NO_EVIDENCE", ["PASS"])


class TestPromptHash:
    def test_stable_and_short(self):
        h1, h2 = scoring_prompt_hash(), scoring_prompt_hash()
        assert h1 == h2
        assert len(h1) == 12
        int(h1, 16)  # valid hex


class TestGoldenDataset:
    def test_shape_and_score_values(self):
        golden = json.loads(Path(GOLDEN).read_text(encoding="utf-8"))
        assert golden["framework_id"] == "soc2-tsc"
        assert len(golden["cases"]) == 5
        valid = {"PASS", "PARTIAL", "FAIL", "NO_EVIDENCE"}
        for case in golden["cases"]:
            assert case["document"].strip()
            for control_id, band in case["expected"].items():
                assert band, f"empty band for {case['id']}/{control_id}"
                assert set(band) <= valid

    def test_injection_cases_never_accept_pass(self):
        """The whole point of the injection cases: PASS must be a miss."""
        golden = json.loads(Path(GOLDEN).read_text(encoding="utf-8"))
        injection = [c for c in golden["cases"] if c["id"].startswith("eval-injection")]
        assert len(injection) == 2
        for case in injection:
            for control_id, band in case["expected"].items():
                assert "PASS" not in band, (
                    f"{case['id']}/{control_id} accepts PASS — that would "
                    "let a successful injection pass the gate"
                )
