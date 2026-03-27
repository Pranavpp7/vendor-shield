"""LangGraph workflow for running a full vendor risk assessment.

Graph: check_documents → evaluate_controls → aggregate_scores → generate_summary
"""

import logging
from typing import TypedDict
from langgraph.graph import StateGraph, END
from supabase import create_client
from config import get_settings
from models.schemas import (
    ControlDefinition, ControlResult, DomainScore, RiskLevel,
    AssessmentResponse,
)
from models.controls import get_all_controls
from services.evaluation import evaluate_all_controls
from services.aggregation import compute_scores, generate_gaps_summary, generate_executive_summary

logger = logging.getLogger(__name__)


# --- State Definition ---

class AssessmentState(TypedDict):
    vendor_name: str
    assessment_id: str
    controls: list[ControlDefinition]
    has_documents: bool
    control_results: list[ControlResult]
    overall_score: int
    risk_level: RiskLevel
    domain_scores: list[DomainScore]
    summary: str
    gaps_summary: str


# --- Node Functions ---

async def check_documents(state: AssessmentState) -> dict:
    """Check if the assessment has indexed documents in Supabase."""
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)
    result = (
        supabase.table("documents")
        .select("id")
        .eq("assessment_id", state["assessment_id"])
        .eq("status", "ready")
        .limit(1)
        .execute()
    )
    has_docs = len(result.data) > 0
    logger.info(f"Assessment {state['assessment_id']}: has_documents={has_docs}")
    return {"has_documents": has_docs}


async def evaluate_controls(state: AssessmentState) -> dict:
    """Evaluate all controls using RAG + LLM."""
    controls = state["controls"]
    results = await evaluate_all_controls(
        controls,
        state["assessment_id"],
        state["vendor_name"],
        state["has_documents"],
    )
    logger.info(f"Evaluated {len(results)} controls for {state['vendor_name']}")
    return {"control_results": results}


async def aggregate_scores(state: AssessmentState) -> dict:
    """Compute overall and per-domain scores."""
    results = state["control_results"]
    overall_score, risk_level, domain_scores = compute_scores(results)
    gaps = generate_gaps_summary(results)
    logger.info(f"Score: {overall_score}/100, Risk: {risk_level.value}")
    return {
        "overall_score": overall_score,
        "risk_level": risk_level,
        "domain_scores": domain_scores,
        "gaps_summary": gaps,
    }


async def generate_summary(state: AssessmentState) -> dict:
    """Generate executive summary using LLM."""
    summary = await generate_executive_summary(
        state["vendor_name"],
        state["overall_score"],
        state["risk_level"].value,
        state["control_results"],
    )
    return {"summary": summary}


# --- Build Graph ---

def build_assessment_graph():
    """Build the LangGraph assessment workflow."""
    workflow = StateGraph(AssessmentState)

    # Add nodes
    workflow.add_node("check_documents", check_documents)
    workflow.add_node("evaluate_controls", evaluate_controls)
    workflow.add_node("aggregate_scores", aggregate_scores)
    workflow.add_node("generate_summary", generate_summary)

    # Define edges (sequential flow)
    workflow.set_entry_point("check_documents")
    workflow.add_edge("check_documents", "evaluate_controls")
    workflow.add_edge("evaluate_controls", "aggregate_scores")
    workflow.add_edge("aggregate_scores", "generate_summary")
    workflow.add_edge("generate_summary", END)

    return workflow.compile()


async def run_assessment(
    vendor_name: str,
    assessment_id: str,
    controls: list[ControlDefinition] | None = None,
) -> AssessmentResponse:
    """Execute the full assessment LangGraph workflow."""
    if controls is None:
        controls = get_all_controls()

    graph = build_assessment_graph()

    initial_state: AssessmentState = {
        "vendor_name": vendor_name,
        "assessment_id": assessment_id,
        "controls": controls,
        "has_documents": False,
        "control_results": [],
        "overall_score": 0,
        "risk_level": RiskLevel.HIGH,
        "domain_scores": [],
        "summary": "",
        "gaps_summary": "",
    }

    final_state = await graph.ainvoke(initial_state)

    return AssessmentResponse(
        assessment_id=assessment_id,
        vendor_name=vendor_name,
        overall_score=final_state["overall_score"],
        risk_level=final_state["risk_level"],
        domain_scores=final_state["domain_scores"],
        control_results=final_state["control_results"],
        summary=final_state["summary"],
        gaps_summary=final_state["gaps_summary"],
    )
