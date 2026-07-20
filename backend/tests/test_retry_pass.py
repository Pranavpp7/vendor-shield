"""Retry pass of the assessment graph: broadened chunks must actually
reach evaluation, and only NO_EVIDENCE controls with NEW evidence are
re-scored (no LLM, no Qdrant — everything below retrieval is stubbed)."""

import json

import pytest

import chains.assessment_graph as graph_mod
import services.evaluation as eval_mod
from chains.assessment_graph import evaluate_node, re_retrieve_node
from models.controls import get_all_controls
from models.schemas import ControlResult, ControlScore


def _state(**kw) -> dict:
    return {
        "vendor_name": "Acme",
        "assessment_id": "aid",
        "framework_id": "nist-800-53",
        "has_documents": True,
        "retrieved_chunks": {},
        "evaluations": {},
        "control_results": [],
        "response": {},
        "retry_count": 0,
        "retry_control_ids": [],
        "warning": "",
        "error": "",
        **kw,
    }


def _chunk(text: str) -> dict:
    """A minimal search_documents result dict."""
    return {"content": text, "document_name": "doc.pdf", "score": 0.9}


def _result(control_id: str, score: ControlScore) -> ControlResult:
    return ControlResult(
        control_id=control_id,
        score=score,
        confidence=0.9,
        reasoning="first pass",
        domain="d",
        title=control_id,
    )


CONTROLS = get_all_controls("nist-800-53")
C0, C1, C2 = CONTROLS[0]["id"], CONTROLS[1]["id"], CONTROLS[2]["id"]


# ── re_retrieve_node: change detection ───────────────────────────────────────


class TestReRetrieveNode:
    @pytest.mark.asyncio
    async def test_only_changed_nonempty_chunks_are_queued(self, monkeypatch):
        """C0 gets new chunks → queued; C1 gets identical chunks → skipped;
        C2 gets nothing → skipped."""
        old = {C0: [_chunk("old")], C1: [_chunk("same")], C2: []}

        def fake_search(query, assessment_id, top_k):
            # Broadened queries embed the control title — identify by it.
            if CONTROLS[0]["title"] in query:
                return [_chunk("new evidence")]
            if CONTROLS[1]["title"] in query:
                return [_chunk("same")]
            return []

        monkeypatch.setattr(graph_mod, "search_documents", fake_search)

        state = _state(
            retrieved_chunks=old,
            evaluations={
                C0: {"score": "NO_EVIDENCE"},
                C1: {"score": "NO_EVIDENCE"},
                C2: {"score": "NO_EVIDENCE"},
            },
        )
        out = await re_retrieve_node(state)

        assert out["retry_count"] == 1
        assert out["retry_control_ids"] == [C0]
        assert out["retrieved_chunks"][C0] == [_chunk("new evidence")]

    @pytest.mark.asyncio
    async def test_scored_controls_are_not_re_queried(self, monkeypatch):
        """Only NO_EVIDENCE controls get a broadened search at all."""
        queried = []

        def fake_search(query, assessment_id, top_k):
            queried.append(query)
            return []

        monkeypatch.setattr(graph_mod, "search_documents", fake_search)

        state = _state(
            evaluations={C0: {"score": "PASS"}, C1: {"score": "NO_EVIDENCE"}},
        )
        out = await re_retrieve_node(state)

        assert len(queried) == 1
        assert CONTROLS[1]["title"] in queried[0]
        assert out["retry_control_ids"] == []


# ── evaluate_node: retry branch ──────────────────────────────────────────────


class TestEvaluateNodeRetryPass:
    @pytest.mark.asyncio
    async def test_retry_rescores_only_queued_controls_with_chunks(self, monkeypatch):
        calls = {}

        async def fake_evaluate_all(assessment_id, framework_id=None,
                                    controls=None, chunks_by_control=None):
            calls["controls"] = controls
            calls["chunks_by_control"] = chunks_by_control
            fresh = []
            for c in controls:
                r = _result(c["id"], ControlScore.PASS)
                r.reasoning = "retry pass"
                fresh.append(r)
            return fresh

        monkeypatch.setattr(graph_mod, "evaluate_all_controls", fake_evaluate_all)

        broadened = {C0: [_chunk("new evidence")]}
        state = _state(
            retry_count=1,
            retry_control_ids=[C0],
            retrieved_chunks=broadened,
            control_results=[
                _result(C0, ControlScore.NO_EVIDENCE),
                _result(C1, ControlScore.PASS),
            ],
            evaluations={C0: {"score": "NO_EVIDENCE"}, C1: {"score": "PASS"}},
        )
        out = await evaluate_node(state)

        # Only the queued control was re-evaluated, against the broadened chunks
        assert [c["id"] for c in calls["controls"]] == [C0]
        assert calls["chunks_by_control"] == broadened

        # Its new verdict replaced the old one; C1 kept its first-pass result
        by_id = {r.control_id: r for r in out["control_results"]}
        assert by_id[C0].score == ControlScore.PASS
        assert by_id[C0].reasoning == "retry pass"
        assert by_id[C1].reasoning == "first pass"
        assert out["evaluations"][C0] == {"score": "PASS"}
        assert len(out["control_results"]) == 2

    @pytest.mark.asyncio
    async def test_retry_with_nothing_new_skips_llm_entirely(self, monkeypatch):
        async def fail_evaluate_all(*a, **kw):  # pragma: no cover
            raise AssertionError("evaluate_all_controls must not be called")

        monkeypatch.setattr(graph_mod, "evaluate_all_controls", fail_evaluate_all)

        state = _state(
            retry_count=1,
            retry_control_ids=[],
            control_results=[_result(C0, ControlScore.NO_EVIDENCE)],
            evaluations={C0: {"score": "NO_EVIDENCE"}},
        )
        out = await evaluate_node(state)

        assert out["control_results"][0].reasoning == "first pass"
        assert out["evaluations"] == {C0: {"score": "NO_EVIDENCE"}}

    @pytest.mark.asyncio
    async def test_first_pass_evaluates_full_framework(self, monkeypatch):
        calls = {}

        async def fake_evaluate_all(assessment_id, framework_id=None,
                                    controls=None, chunks_by_control=None):
            calls["controls"] = controls
            calls["chunks_by_control"] = chunks_by_control
            return [_result(C0, ControlScore.PASS)]

        monkeypatch.setattr(graph_mod, "evaluate_all_controls", fake_evaluate_all)

        await evaluate_node(_state())

        assert calls["controls"] is None            # default → whole framework
        assert calls["chunks_by_control"] is None   # default → own retrieval


# ── evaluate_control: chunks override bypasses retrieval ─────────────────────


class TestEvaluateControlChunksOverride:
    @pytest.mark.asyncio
    async def test_provided_chunks_skip_retrieval(self, monkeypatch):
        def fail_search(*a, **kw):  # pragma: no cover
            raise AssertionError("search_documents must not be called")

        async def fake_llm(prompt, assessment_id):
            assert "broadened chunk text" in prompt
            return json.dumps({
                "control_id": CONTROLS[0]["id"],
                "score": "PASS",
                "confidence": 0.9,
                "evidence_quote": "broadened chunk text",
                "evidence_chunk": 1,
                "reasoning": "grounded in the provided chunk",
                "gap": None,
            })

        monkeypatch.setattr(eval_mod, "search_documents", fail_search)
        monkeypatch.setattr(eval_mod, "_call_llm_json", fake_llm)

        result = await eval_mod.evaluate_control(
            CONTROLS[0], "aid", chunks=[_chunk("broadened chunk text")],
        )

        assert result.score == ControlScore.PASS
        assert result.citations[0].document == "doc.pdf"
