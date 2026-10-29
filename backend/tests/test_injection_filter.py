"""Deterministic scoring-injection filters — no LLM, no Qdrant."""

from pathlib import Path
import json

from models.controls import get_scoring_prompt
from services.evaluation import (
    chunk_looks_like_score_injection,
    filter_injected_chunks,
    quote_only_in_injection_scaffold,
)

GOLDEN = Path(__file__).resolve().parent.parent / "evals" / "golden_vendors.json"


def _injection_document() -> str:
    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))["cases"]
    for case in cases:
        if case["id"] == "eval-injection-fake-json":
            return case["document"]
    raise AssertionError("eval-injection-fake-json missing from golden_vendors.json")


INJECTION_DOC = _injection_document()
ATTACK_QUOTE = "CloudNine maintains industry-leading security controls"


class TestChunkLooksLikeScoreInjection:
    def test_golden_attack_paragraph_is_poisoned(self):
        assert chunk_looks_like_score_injection(INJECTION_DOC)

    def test_real_self_attestation_is_kept(self):
        text = (
            "All customer data at rest is encrypted with AES-256; "
            "keys live in a dedicated KMS with annual rotation."
        )
        assert not chunk_looks_like_score_injection(text)


class TestFilterInjectedChunks:
    def test_drops_poisoned_keeps_clean(self):
        rows = [
            {"content": INJECTION_DOC, "score": 0.9},
            {"content": "MFA with hardware keys is mandatory for every employee.", "score": 0.8},
        ]
        kept = filter_injected_chunks(rows)
        assert len(kept) == 1
        assert "MFA" in kept[0]["content"]

    def test_all_poisoned_yields_empty(self):
        assert filter_injected_chunks([{"content": INJECTION_DOC}]) == []


class TestQuoteOnlyInInjectionScaffold:
    def test_cloudnine_attack_quote(self):
        assert quote_only_in_injection_scaffold(ATTACK_QUOTE, [INJECTION_DOC])

    def test_real_sentence_in_same_doc_is_not_scaffold_only(self):
        real = (
            "We believe security is a shared responsibility and we are always "
            "happy to discuss our practices with customers during the sales process."
        )
        assert not quote_only_in_injection_scaffold(real, [INJECTION_DOC])

    def test_clean_doc_quote_is_standalone(self):
        doc = "Our 24/7 SOC monitors a central SIEM with 13-month log retention."
        quote = "Our 24/7 SOC monitors a central SIEM with 13-month log retention."
        assert not quote_only_in_injection_scaffold(quote, [doc])


class TestScoringPromptFence:
    def test_vendor_document_delimiters_present(self):
        control = {
            "id": "AC-001",
            "ref": "CC6.1",
            "title": "Logical access",
            "description": "Access is restricted.",
            "what_good_looks_like": "MFA everywhere.",
            "what_to_look_for": "MFA",
        }
        prompt = get_scoring_prompt(control, ["We enforce MFA for all employees."])
        assert "<<<VENDOR_DOCUMENT>>>" in prompt
        assert "<<<END_VENDOR_DOCUMENT>>>" in prompt
        assert "untrusted DATA" in prompt
        assert "We enforce MFA for all employees." in prompt
