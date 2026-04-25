"""Layer 5: LangGraph Agent — full vendor risk assessment workflow.

RESPONSIBILITY:
    Orchestrates the end-to-end assessment pipeline as a LangGraph
    state machine.  This is the only file that wires the services
    together into a complete workflow.

    Graph:
        check_documents ──┬── has docs ──→ evaluate_controls ──→ aggregate ──→ save_results
                          └── no docs  ──→ aggregate (all NO_EVIDENCE) ──→ save_results

    Each node delegates to services/storage — no business logic here,
    only coordination.

IMPORTS FROM: storage/qdrant_store, services/evaluation, services/aggregation,
              storage/local_store, models/schemas, models/controls
IMPORTED BY:  mcp/server.py
"""

import asyncio
import logging
from typing import TypedDict

from langgraph.graph import StateGraph, END

from models.schemas import AssessmentResponse, ControlResult, ControlScore
from models.controls import get_all_controls
from storage.qdrant_store import get_collection_stats
from services.evaluation import evaluate_all_controls
from services.aggregation import aggregate_results
from storage.local_store import save_assessment, update_assessment, get_assessment

logger = logging.getLogger(__name__)


# ── State Definition ─────────────────────────────────────────────────────────


class AssessmentState(TypedDict):
    """Data that flows through the graph from node to node."""
    vendor_name: str
    assessment_id: str
    has_documents: bool
    control_results: list          # list[ControlResult]
    response: dict                 # serialized AssessmentResponse


# ── Node Functions ───────────────────────────────────────────────────────────
# Each node reads from state, calls ONE service, writes results back.


async def check_documents(state: AssessmentState) -> dict:
    """Check whether the assessment has indexed documents in Qdrant.

    Delegates to: storage/qdrant_store.get_collection_stats()
    """
    assessment_id = state["assessment_id"]
    try:
        stats = get_collection_stats(assessment_id)
        has_docs = stats.get("vector_count", 0) > 0
    except Exception as e:
        logger.warning(f"Could not check documents for {assessment_id}: {e}")
        has_docs = False

    logger.info(
        f"Assessment {assessment_id}: has_documents={has_docs}"
    )
    return {"has_documents": has_docs}


def _route_after_check(state: AssessmentState) -> str:
    """Conditional edge: skip LLM evaluation if no documents exist."""
    if state["has_documents"]:
        return "evaluate_controls"
    return "aggregate"


async def evaluate_controls(state: AssessmentState) -> dict:
    """Score all 20 controls against vendor documents using RAG + LLM.

    Delegates to: services/evaluation.evaluate_all_controls()
    Runs concurrently (5 threads) for 10-15x speedup.
    """
    assessment_id = state["assessment_id"]
    results = await asyncio.to_thread(evaluate_all_controls, assessment_id)
    logger.info(
        f"Evaluated {len(results)} controls for "
        f"vendor '{state['vendor_name']}'"
    )
    return {"control_results": results}


async def aggregate(state: AssessmentState) -> dict:
    """Compute domain scores, overall score, risk level, and gaps summary.

    If no documents were found, creates NO_EVIDENCE results for all 20
    controls so the report still shows every control with a clear status.

    Delegates to: services/aggregation.aggregate_results()
    """
    control_results = state["control_results"]

    # If we skipped evaluation (no documents), build NO_EVIDENCE stubs
    if not control_results:
        controls = get_all_controls()
        control_results = [
            ControlResult(
                control_id=c["id"],
                score=ControlScore.NO_EVIDENCE,
                confidence="LOW",
                reasoning="No vendor documents were uploaded for evaluation.",
                gap="Upload vendor security documentation to evaluate this control.",
                domain=c["domain"],
                title=c["title"],
            )
            for c in controls
        ]

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

    Delegates to: storage/local_store.save_assessment() / update_assessment()
    """
    assessment_id = state["assessment_id"]
    report_data = state["response"]

    # Add status field for the UI
    report_data["status"] = "completed"
    report_data["vendor_name"] = state["vendor_name"]

    # Save or update
    existing = get_assessment(assessment_id)
    if existing:
        update_assessment(assessment_id, report_data)
        logger.info(f"Updated assessment {assessment_id}")
    else:
        save_assessment(assessment_id, report_data)
        logger.info(f"Saved new assessment {assessment_id}")

    return {}


# ── Build Graph ──────────────────────────────────────────────────────────────


def build_assessment_graph():
    """Build and compile the LangGraph assessment workflow.

    Graph structure:
        check_documents ──┬── has_documents=True  ──→ evaluate_controls → aggregate → save_results
                          └── has_documents=False ──→ aggregate → save_results
    """
    workflow = StateGraph(AssessmentState)

    # Add nodes
    workflow.add_node("check_documents", check_documents)
    workflow.add_node("evaluate_controls", evaluate_controls)
    workflow.add_node("aggregate", aggregate)
    workflow.add_node("save_results", save_results)

    # Entry point
    workflow.set_entry_point("check_documents")

    # Conditional edge: skip evaluation if no documents
    workflow.add_conditional_edges(
        "check_documents",
        _route_after_check,
        {
            "evaluate_controls": "evaluate_controls",
            "aggregate": "aggregate",
        },
    )

    # Linear edges for the rest
    workflow.add_edge("evaluate_controls", "aggregate")
    workflow.add_edge("aggregate", "save_results")
    workflow.add_edge("save_results", END)

    return workflow.compile()


# ── Public API ───────────────────────────────────────────────────────────────


async def run_assessment(
    vendor_name: str,
    assessment_id: str,
) -> AssessmentResponse:
    """Execute the full assessment LangGraph workflow.

    This is the single entry point called by mcp/server.py.
    Signature matches what the MCP server's guarded import expects.

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
        "control_results": [],
        "response": {},
    }

    final_state = await graph.ainvoke(initial_state)

    # Reconstruct the typed response from the serialized dict
    return AssessmentResponse(**final_state["response"])
