"""LLM-output parsers and text utilities — the fragile edges, no LLM needed."""

import json

import pytest

from services.chunking import split_text
from services.evaluation import _parse_confidence, _parse_llm_json
from services.followup import _parse_questions
from services.framework_extraction import _parse_draft, slugify


class TestParseLlmJson:
    def test_clean_json(self):
        parsed = _parse_llm_json('{"control_id": "A-1", "score": "PASS"}', "A-1")
        assert parsed["score"] == "PASS"

    def test_markdown_fences_stripped(self):
        raw = '```json\n{"control_id": "A-1", "score": "FAIL"}\n```'
        assert _parse_llm_json(raw, "A-1")["score"] == "FAIL"

    def test_bare_fences_stripped(self):
        # Regression: some OpenRouter providers wrap JSON in plain ``` fences
        # (no language tag) — caught by the golden-dataset evals
        raw = '```\n{"control_id": "A-1", "score": "PASS"}\n```'
        assert _parse_llm_json(raw, "A-1")["score"] == "PASS"

    def test_json_with_surrounding_prose_recovered(self):
        raw = 'Here is my assessment:\n{"control_id": "A-1", "score": "PARTIAL"}\nHope this helps!'
        assert _parse_llm_json(raw, "A-1")["score"] == "PARTIAL"

    def test_garbage_falls_back_to_no_evidence(self):
        parsed = _parse_llm_json("I am not JSON at all", "A-1")
        assert parsed["score"] == "NO_EVIDENCE"
        assert parsed["control_id"] == "A-1"
        assert parsed["confidence"] == 0.0


class TestParseConfidence:
    @pytest.mark.parametrize("raw,expected", [
        (0.85, 0.85),
        (1.7, 1.0),        # clamped high
        (-3, 0.0),         # clamped low
        ("HIGH", 0.85),    # legacy strings
        ("low", 0.15),
        ("garbage", 0.5),  # unparseable → neutral
        (None, 0.5),
    ])
    def test_values(self, raw, expected):
        assert _parse_confidence(raw) == expected


class TestParseQuestions:
    def test_valid_array(self):
        raw = json.dumps([
            {"control_id": "A-1", "domain": "D", "question": "Q?", "rationale": "R"}
        ])
        questions = _parse_questions(raw)
        assert len(questions) == 1 and questions[0]["question"] == "Q?"

    def test_prose_around_array_tolerated(self):
        raw = 'Here are the questions:\n[{"control_id": "A-1", "question": "Q?"}]\nDone.'
        assert len(_parse_questions(raw)) == 1

    def test_entries_without_question_dropped(self):
        raw = json.dumps([
            {"control_id": "A-1", "question": "Q?"},
            {"control_id": "A-2", "question": ""},
        ])
        assert len(_parse_questions(raw)) == 1


class TestParseDraft:
    def test_fenced_object(self):
        raw = '```json\n{"name": "FW", "controls": [{"id": "A-1"}]}\n```'
        assert _parse_draft(raw)["name"] == "FW"

    def test_non_object_raises(self):
        with pytest.raises(Exception):
            _parse_draft('["not", "a", "framework"]')


class TestSlugify:
    @pytest.mark.parametrize("name,expected", [
        ("ACME Vendor Questionnaire", "acme-vendor-questionnaire"),
        ("ISO 27001:2022 (Annex A)", "iso-27001-2022-annex-a"),
        ("!!!", "custom-framework"),
    ])
    def test_slugs(self, name, expected):
        assert slugify(name) == expected


class TestSplitText:
    # split_text works in characters under the hood (words × 6 chars via
    # LangChain's RecursiveCharacterTextSplitter), so assertions target the
    # character budget and overlap behavior, not exact word counts.

    def test_empty_input_returns_empty_list(self):
        assert split_text("") == []
        assert split_text("   \n  ") == []

    def test_short_text_single_chunk(self):
        assert split_text("one two three", chunk_size=500, chunk_overlap=50) == ["one two three"]

    def test_character_budget_respected(self):
        words = " ".join(f"w{i}" for i in range(1000))
        chunks = split_text(words, chunk_size=100, chunk_overlap=10)
        assert len(chunks) > 1
        assert all(len(c) <= 100 * 6 for c in chunks)  # size_words × CHARS_PER_WORD

    def test_consecutive_chunks_overlap(self):
        words = " ".join(f"w{i}" for i in range(1000))
        chunks = split_text(words, chunk_size=100, chunk_overlap=10)
        for first, second in zip(chunks, chunks[1:]):
            # The tail of each chunk reappears at the start of the next
            assert set(first.split()[-3:]) & set(second.split())

    def test_no_content_lost(self):
        words = [f"w{i}" for i in range(350)]
        chunks = split_text(" ".join(words), chunk_size=100, chunk_overlap=10)
        seen = set()
        for c in chunks:
            seen.update(c.split())
        assert seen == set(words)
