"""Layer 5: LangGraph Agent — dynamic vendor risk assessment workflow.

RESPONSIBILITY:
    Orchestrates the end-to-end assessment pipeline as a LangGraph
    state machine with conditional edges.  This is the only file that
    wires the services together into a complete workflow.

    Graph (dynamic):
        ingest_node
          ├─(no docs)──────────────────────────────→ no_documents_node
          └─(has docs)──→ retrieve_node
                              ├─(no_documents)──→ no_documents_node ──→ save_results ──→ END
                              ├─(sparse_evidence)─→ sparse_evidence_node ──→ evaluate_node
                              └─(evaluate)────────→ evaluate_node
                                                        ├─(re_retrieve)──→ re_retrieve_node ──→ evaluate_node
                                                        └─(aggregate)──→ aggregate_node ──→ save_results ──→ END

IMPORTS FROM: storage/qdrant_store, services/evaluation, services/aggregation,
              services/retrieval, services/progress, storage/local_store,
              models/schemas, models/controls, config
IMPORTED BY:  mcp/server.py
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import StateGraph, END

from config import get_settings
from models.schemas import AssessmentResponse, ControlResult, ControlScore
from models.controls import get_all_controls
from storage.qdrant_store import get_collection_stats
from services.evaluation import evaluate_all_controls
from services.aggregation import aggregate_results
from services.retrieval import search_documents
from services.progress import set_progress, clear_progress
from storage.local_store import save_assessment, update_assessment, get_assessment

logger = logging.getLogger(__name__)


# ── State Definition ─────────────────────────────────────────────────────────


class AssessmentState(TypedDict):
    """Data that flows through the graph from node to node."""
    vendor_name: str
    assessment_id: str
    has_documents: bool
    retrieved_chunks: dict      # {control_id: list[chunk_dicts]} — for routing decisions
    evaluations: dict           # {control_id: {"score": str}} — built after evaluate_node
    control_results: list       # list[ControlResult] — for aggregation
    response: dict              # serialized AssessmentResponse
    retry_count: int            # incremented by re_retrieve_node; capped at 1
    warning: str                # set on sparse_evidence path
    error: str                  # set on no_documents path


# ── Routing Functions ────────────────────────────────────────────────────────


def route_after_ingest(state: AssessmentState) -> str:
    """Skip the 20 retrieval calls entirely when Qdrant has no vectors at all."""
    if not state["has_documents"]:
        logger.info("Ingest shortcut: no documents → going directly to no_documents_node")
        return "no_documents"
    return "retrieve"


def route_after_retrieve(state: AssessmentState) -> str:
    """Decide whether to evaluate, warn, or abort based on chunk coverage."""
    retrieved = state.get("retrieved_chunks", {})
    controls_with_chunks = sum(
        1 for chunks in retrieved.values() if len(chunks) > 0
    )
    total_controls = len(retrieved)

    if controls_with_chunks == 0:
        route = "no_documents"
    elif controls_with_chunks < total_controls * 0.5:
        route = "sparse_evidence"
    else:
        route = "evaluate"

    logger.info(
        f"Route after retrieve: {controls_with_chunks}/{total_controls} "
        f"controls have chunks → {route}"
    )
    return route


def route_after_evaluate(state: AssessmentState) -> str:
    """Retry evaluation with broader retrieval if >60% controls have NO_EVIDENCE."""
    evaluations = state.get("evaluations", {})
    total = len(evaluations)
    if total == 0:
        return "aggregate"

    no_evidence_count = sum(
        1 for e in evaluations.values()
        if e.get("score") == "NO_EVIDENCE"
    )
    no_evidence_ratio = no_evidence_count / total
    retry_count = state.get("retry_count", 0)

    if no_evidence_ratio > 0.6 and retry_count < 1:
        route = "re_retrieve"
    else:
        route = "aggregate"

    logger.info(
        f"Route after evaluate: {no_evidence_count}/{total} "
        f"NO_EVIDENCE ({no_evidence_ratio:.0%}) → {route}"
    )
    return route


# ── Node Functions ───────────────────────────────────────────────────────────


async def ingest_node(state: AssessmentState) -> dict:
    """Check whether the assessment has indexed documents in Qdrant."""
    assessment_id = state["assessment_id"]
    set_progress(assessment_id, "ingest", "Checking indexed documents…", 5)

    try:
        stats = get_collection_stats(assessment_id)
        has_docs = stats.get("vector_count", 0) > 0
    except Exception as e:
        logger.warning(f"Could not check documents for {assessment_id}: {e}")
        has_docs = False

    logger.info(f"Assessment {assessment_id}: has_documents={has_docs}")
    return {"has_documents": has_docs}


async def retrieve_node(state: AssessmentState) -> dict:
    """Pre-fetch document chunks for all controls to enable routing decisions.

    Runs all 20 retrieval queries concurrently.  The result is stored in
    state["retrieved_chunks"] and used ONLY for routing — evaluate_node
    does its own internal retrieval for the actual LLM scoring.
    """
    assessment_id = state["assessment_id"]
    set_progress(assessment_id, "retrieve", "Retrieving evidence chunks…", 15)
    settings = get_settings()
    controls = get_all_controls()

    async def _fetch_one(control: dict) -> tuple[str, list[dict]]:
        try:
            chunks = await asyncio.to_thread(
                search_documents,
                control["search_query"],
                assessment_id,
                settings.retrieval_top_k,
            )
            return control["id"], chunks
        except Exception as e:
            logger.warning(f"Retrieval failed for {control['id']}: {e}")
            return control["id"], []

    pairs = await asyncio.gather(*[_fetch_one(c) for c in controls])
    retrieved_chunks = dict(pairs)

    total = len(retrieved_chunks)
    covered = sum(1 for v in retrieved_chunks.values() if v)
    logger.info(f"Retrieve complete: {covered}/{total} controls have chunks")
    return {"retrieved_chunks": retrieved_chunks}


async def no_documents_node(state: AssessmentState) -> dict:
    """Handle the case where no relevant chunks exist for any control.

    Builds NO_EVIDENCE stubs for all 20 controls and aggregates them
    into a zero-score response without making any LLM calls.
    """
    assessment_id = state["assessment_id"]
    vendor_name = state["vendor_name"]
    set_progress(assessment_id, "no_documents", "No document content found — skipping evaluation…", 80)

    logger.warning(
        f"Assessment {assessment_id}: no relevant chunks found — "
        "skipping LLM evaluation entirely"
    )

    controls = get_all_controls()
    control_results = [
        ControlResult(
            control_id=c["id"],
            score=ControlScore.NO_EVIDENCE,
            confidence="LOW",
            reasoning="No relevant content found in vendor documents.",
            gap="Upload vendor security documentation to evaluate this control.",
            domain=c["domain"],
            title=c["title"],
        )
        for c in controls
    ]

    response = aggregate_results(
        assessment_id=assessment_id,
        vendor_name=vendor_name,
        control_results=control_results,
    )

    logger.info(
        f"No-documents path: score={response.overall_score}/100, "
        f"risk={response.risk_level.value}"
    )
    return {
        "error": "No relevant content found in vendor documents",
        "control_results": control_results,
        "response": response.model_dump(mode="json"),
    }


async def sparse_evidence_node(state: AssessmentState) -> dict:
    """Warn that fewer than 50% of controls have evidence, then continue."""
    assessment_id = state["assessment_id"]
    retrieved = state.get("retrieved_chunks", {})
    covered = sum(1 for v in retrieved.values() if v)
    total = len(retrieved)
    set_progress(assessment_id, "sparse_evidence", f"Sparse evidence ({covered}/{total} controls) — continuing evaluation…", 25)

    logger.warning(
        f"Sparse evidence: only {covered}/{total} controls have chunks — "
        "proceeding with evaluation but results may be incomplete"
    )
    return {
        "warning": (
            "Less than 50% of controls have supporting evidence — "
            "results may be incomplete"
        )
    }


async def evaluate_node(state: AssessmentState) -> dict:
    """Score all 20 controls against vendor documents using RAG + LLM.

    Delegates to services/evaluation.evaluate_all_controls() which runs
    its own internal retrieval + Groq LLM calls concurrently (5 threads).
    """
    assessment_id = state["assessment_id"]
    retry = state.get("retry_count", 0)
    msg = "Evaluating 20 security controls…" if retry == 0 else f"Re-evaluating controls (retry {retry})…"
    set_progress(assessment_id, "evaluate", msg, 35 if retry == 0 else 65)

    results = await asyncio.to_thread(evaluate_all_controls, assessment_id)

    evaluations = {r.control_id: {"score": r.score.value} for r in results}

    set_progress(assessment_id, "evaluate_done", "Controls evaluated, analysing results…", 75)
    logger.info(
        f"Evaluated {len(results)} controls for vendor '{state['vendor_name']}'"
    )
    return {
        "control_results": results,
        "evaluations": evaluations,
    }


async def re_retrieve_node(state: AssessmentState) -> dict:
    """Broaden retrieval queries for NO_EVIDENCE controls and retry evaluation.

    For each control that scored NO_EVIDENCE, concatenates search_query +
    title + description[:100] to widen the semantic search surface.
    """
    assessment_id = state["assessment_id"]
    settings = get_settings()
    retry_count = state.get("retry_count", 0) + 1

    evaluations = state.get("evaluations", {})
    retrieved_chunks = dict(state.get("retrieved_chunks", {}))
    controls_by_id = {c["id"]: c for c in get_all_controls()}

    no_evidence_ids = [
        cid for cid, e in evaluations.items()
        if e.get("score") == "NO_EVIDENCE"
    ]

    set_progress(assessment_id, "re_retrieve", f"Broadening search for {len(no_evidence_ids)} controls with no evidence…", 55)
    logger.info(
        f"Re-retrieve pass {retry_count}: broadening queries for "
        f"{len(no_evidence_ids)} NO_EVIDENCE controls"
    )

    async def _fetch_broader(control_id: str) -> tuple[str, list[dict]]:
        control = controls_by_id.get(control_id)
        if not control:
            return control_id, []
        broader_query = (
            control["search_query"] + " "
            + control["title"] + " "
            + control.get("description", "")[:100]
        )
        try:
            chunks = await asyncio.to_thread(
                search_documents,
                broader_query,
                assessment_id,
                settings.retrieval_top_k,
            )
            return control_id, chunks
        except Exception as e:
            logger.warning(f"Broad retrieval failed for {control_id}: {e}")
            return control_id, retrieved_chunks.get(control_id, [])

    pairs = await asyncio.gather(*[_fetch_broader(cid) for cid in no_evidence_ids])
    for control_id, chunks in pairs:
        retrieved_chunks[control_id] = chunks

    return {
        "retry_count": retry_count,
        "retrieved_chunks": retrieved_chunks,
    }


async def aggregate_node(state: AssessmentState) -> dict:
    """Compute domain scores, overall score, risk level, and gaps summary."""
    assessment_id = state["assessment_id"]
    set_progress(assessment_id, "aggregate", "Calculating domain scores and risk level…", 85)

    control_results = state["control_results"]

    response = aggregate_results(
        assessment_id=state["assessment_id"],
        vendor_name=state["vendor_name"],
        control_results=control_results,
    )

    logger.info(
        f"Aggregated: score={response.overall_score}/100, "
        f"risk={response.risk_level.value}"
    )
    return {
        "control_results": control_results,
        "response": response.model_dump(mode="json"),
    }


async def save_results(state: AssessmentState) -> dict:
    """Persist the assessment results to local JSON storage.

    Also appends a run history entry to the assessment record so the
    frontend can show score trends over multiple runs.
    """
    assessment_id = state["assessment_id"]
    set_progress(assessment_id, "saving", "Saving assessment results…", 95)

    report_data = state["response"]
    report_data["status"] = "completed"
    report_data["vendor_name"] = state["vendor_name"]

    if state.get("warning"):
        report_data["warning"] = state["warning"]
    if state.get("error"):
        report_data["error"] = state["error"]

    # Build a run history entry
    cr_list = report_data.get("control_results", [])
    run_entry = {
        "run_id": uuid.uuid4().hex[:8],
        "score": report_data.get("overall_score", 0),
        "risk_level": report_data.get("risk_level", "High"),
        "pass_count": sum(1 for c in cr_list if c.get("score") == "PASS"),
        "fail_count": sum(1 for c in cr_list if c.get("score") == "FAIL"),
        "no_evidence_count": sum(1 for c in cr_list if c.get("score") == "NO_EVIDENCE"),
        "partial_count": sum(1 for c in cr_list if c.get("score") == "PARTIAL"),
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }

    existing = get_assessment(assessment_id)
    prev_history = existing.get("run_history", []) if existing else []
    report_data["run_history"] = prev_history + [run_entry]

    if existing:
        update_assessment(assessment_id, report_data)
        logger.info(f"Updated assessment {assessment_id}")
    else:
        save_assessment(assessment_id, report_data)
        logger.info(f"Saved new assessment {assessment_id}")

    set_progress(assessment_id, "complete", "Assessment complete", 100)
    clear_progress(assessment_id)
    return {}


# ── Build Graph ──────────────────────────────────────────────────────────────


def build_assessment_graph():
    """Build and compile the dynamic LangGraph assessment workflow."""
    workflow = StateGraph(AssessmentState)

    workflow.add_node("ingest_node", ingest_node)
    workflow.add_node("retrieve_node", retrieve_node)
    workflow.add_node("no_documents_node", no_documents_node)
    workflow.add_node("sparse_evidence_node", sparse_evidence_node)
    workflow.add_node("evaluate_node", evaluate_node)
    workflow.add_node("re_retrieve_node", re_retrieve_node)
    workflow.add_node("aggregate_node", aggregate_node)
    workflow.add_node("save_results", save_results)

    workflow.set_entry_point("ingest_node")

    # Shortcut: skip all 20 retrieval calls if Qdrant has no vectors at all
    workflow.add_conditional_edges(
        "ingest_node",
        route_after_ingest,
        {
            "no_documents": "no_documents_node",
            "retrieve": "retrieve_node",
        },
    )

    workflow.add_conditional_edges(
        "retrieve_node",
        route_after_retrieve,
        {
            "no_documents": "no_documents_node",
            "sparse_evidence": "sparse_evidence_node",
            "evaluate": "evaluate_node",
        },
    )

    workflow.add_edge("no_documents_node", "save_results")
    workflow.add_edge("sparse_evidence_node", "evaluate_node")

    workflow.add_conditional_edges(
        "evaluate_node",
        route_after_evaluate,
        {
            "re_retrieve": "re_retrieve_node",
            "aggregate": "aggregate_node",
        },
    )

    # Cycle: re_retrieve → evaluate (retry_count cap prevents infinite loop)
    workflow.add_edge("re_retrieve_node", "evaluate_node")

    workflow.add_edge("aggregate_node", "save_results")
    workflow.add_edge("save_results", END)

    return workflow.compile()


# ── Public API ───────────────────────────────────────────────────────────────


async def run_assessment(
    vendor_name: str,
    assessment_id: str,
) -> AssessmentResponse:
    """Execute the full assessment LangGraph workflow.

    This is the single entry point called by mcp/server.py.

    Args:
        vendor_name: Name of the vendor being assessed.
        assessment_id: Unique ID for this assessment.

    Returns:
        Complete AssessmentResponse with scores, control results, and gaps.
    """
    logger.info(
        f"Starting assessment for '{vendor_name}' "
        f"(assessment_id={assessment_id})"
    )

    graph = build_assessment_graph()

    initial_state: AssessmentState = {
        "vendor_name": vendor_name,
        "assessment_id": assessment_id,
        "has_documents": False,
        "retrieved_chunks": {},
        "evaluations": {},
        "control_results": [],
        "response": {},
        "retry_count": 0,
        "warning": "",
        "error": "",
    }

    final_state = await graph.ainvoke(initial_state)

    return AssessmentResponse(**final_state["response"])
