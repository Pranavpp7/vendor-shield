"""LangGraph routing functions — pure logic, no LLM, no MCP calls."""

from chains.assessment_graph import (
    route_after_evaluate,
    route_after_ingest,
    route_after_retrieve,
)


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
        "warning": "",
        "error": "",
        **kw,
    }


class TestRouteAfterIngest:
    def test_no_documents_shortcut(self):
        assert route_after_ingest(_state(has_documents=False)) == "no_documents"

    def test_documents_go_to_retrieve(self):
        assert route_after_ingest(_state(has_documents=True)) == "retrieve"


class TestRouteAfterRetrieve:
    def test_zero_coverage_aborts(self):
        chunks = {f"C-{i}": [] for i in range(10)}
        assert route_after_retrieve(_state(retrieved_chunks=chunks)) == "no_documents"

    def test_sparse_coverage_warns(self):
        # 4 of 10 covered → under the 50% threshold
        chunks = {f"C-{i}": (["x"] if i < 4 else []) for i in range(10)}
        assert route_after_retrieve(_state(retrieved_chunks=chunks)) == "sparse_evidence"

    def test_exactly_half_evaluates(self):
        chunks = {f"C-{i}": (["x"] if i < 5 else []) for i in range(10)}
        assert route_after_retrieve(_state(retrieved_chunks=chunks)) == "evaluate"

    def test_full_coverage_evaluates(self):
        chunks = {f"C-{i}": ["x"] for i in range(10)}
        assert route_after_retrieve(_state(retrieved_chunks=chunks)) == "evaluate"


class TestRouteAfterEvaluate:
    def _evals(self, no_evidence: int, total: int) -> dict:
        return {
            f"C-{i}": {"score": "NO_EVIDENCE" if i < no_evidence else "PASS"}
            for i in range(total)
        }

    def test_mostly_no_evidence_triggers_retry(self):
        state = _state(evaluations=self._evals(7, 10))  # 70% > 60%
        assert route_after_evaluate(state) == "re_retrieve"

    def test_exactly_60pct_does_not_retry(self):
        state = _state(evaluations=self._evals(6, 10))  # 60% is not > 60%
        assert route_after_evaluate(state) == "aggregate"

    def test_retry_happens_only_once(self):
        state = _state(evaluations=self._evals(9, 10), retry_count=1)
        assert route_after_evaluate(state) == "aggregate"

    def test_empty_evaluations_aggregate(self):
        assert route_after_evaluate(_state(evaluations={})) == "aggregate"
