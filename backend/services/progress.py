"""
Layer 3: Assessment run progress — shared in-memory state for SSE streaming.

RESPONSIBILITY:
    A single dict, keyed by assessment_id, holding the latest progress
    event {step, message, percent}.  The LangGraph nodes and the
    evaluation service WRITE to it; the assessments router's SSE
    endpoint READS from it.  Living in the services layer lets both the
    graph (Layer 5) and routers (Layer 6) import it without a cycle.

    Step names are part of the frontend contract — the pipeline stepper
    in the UI maps them to stages:
        ingest → retrieve → sparse_evidence → evaluate → re_retrieve
        → aggregate → save → complete | no_documents | error

    Sufficient for single-process deployments; replace with Redis
    pub/sub if horizontal scaling is ever needed.

IMPORTS FROM: nothing
IMPORTED BY:  routers/assessments.py, chains/assessment_graph.py,
              services/evaluation.py
"""

_progress: dict[str, dict] = {}


def set_progress(assessment_id: str, step: str, message: str, percent: int) -> None:
    """Record the latest progress event for an assessment run."""
    _progress[assessment_id] = {
        "step": step,
        "message": message,
        "percent": max(0, min(100, percent)),
    }


def get_progress(assessment_id: str) -> dict:
    """Return the latest event, or an idle placeholder."""
    return _progress.get(
        assessment_id, {"step": "idle", "message": "", "percent": 0}
    )


def clear_progress(assessment_id: str) -> None:
    """Drop the stored state once a run has finished streaming."""
    _progress.pop(assessment_id, None)
