"""Control evaluation engine using LangChain + Groq (Llama 3.3 70B)."""

import json
import logging
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from config import get_settings
from models.schemas import ControlDefinition, ControlResult, ControlStatus, RiskLevel, Citation
from services.retrieval import retrieve_evidence_for_control

logger = logging.getLogger(__name__)

EVAL_SYSTEM_PROMPT = """You are a rigorous vendor security assessor. Evaluate the given control STRICTLY based on the document evidence provided.

RULES:
- "Pass" — clear, specific evidence in documents that the control requirement is met.
- "Partial" — documents partially address the control but lack sufficient detail for full compliance.
- "Fail" — documents explicitly show non-compliance or contradictory evidence.
- "No Evidence" — no relevant evidence exists in the documents for this control.
- In the rationale, cite the SPECIFIC document name and what evidence you found (or didn't find).
- Set risk_level based on the severity: "High" if critical security gap, "Medium" if partial gap, "Low" if compliant.

Respond with ONLY valid JSON (no markdown code blocks):
{{"status": "Pass"|"Partial"|"Fail"|"No Evidence", "rationale": "2-3 sentence explanation", "risk_level": "Low"|"Medium"|"High"}}"""

EVAL_NO_DOCS_SYSTEM_PROMPT = """You are generating a preliminary vendor security checklist assessment. No documents have been uploaded yet.

RULES:
- Without documents, most controls should be "No Evidence" status.
- Only well-known, publicly verifiable items for famous vendors may be "Pass" if you cite a specific public source.
- In the rationale, clearly state no documents are available.

Respond with ONLY valid JSON (no markdown code blocks):
{{"status": "Pass"|"Partial"|"Fail"|"No Evidence", "rationale": "2-3 sentence explanation", "risk_level": "Low"|"Medium"|"High"}}"""


def _get_llm():
    settings = get_settings()
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=0.3,
        max_tokens=500,
    )


async def evaluate_single_control(
    control: ControlDefinition,
    assessment_id: str,
    vendor_name: str,
    has_documents: bool = False,
) -> ControlResult:
    """Evaluate a single control using retrieved evidence and LLM."""
    evidence_text = ""
    citations: list[Citation] = []

    if has_documents:
        evidence_text, citations = retrieve_evidence_for_control(
            assessment_id, control.name
        )

    llm = _get_llm()
    system_prompt = EVAL_SYSTEM_PROMPT if has_documents else EVAL_NO_DOCS_SYSTEM_PROMPT

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Vendor: {vendor_name}\nControl: {control_id}: {control_name}\nDescription: {control_description}\n\n{evidence}"),
    ])

    chain = prompt | llm

    evidence_block = f"DOCUMENT EVIDENCE:\n{evidence_text}" if evidence_text else "NO DOCUMENTS UPLOADED"

    try:
        response = await chain.ainvoke({
            "vendor_name": vendor_name,
            "control_id": control.id,
            "control_name": control.name,
            "control_description": control.description,
            "evidence": evidence_block,
        })

        # Parse JSON response
        content = response.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(content)

        status_map = {
            "Pass": ControlStatus.PASS,
            "Partial": ControlStatus.PARTIAL,
            "Fail": ControlStatus.FAIL,
            "No Evidence": ControlStatus.NO_EVIDENCE,
        }
        risk_map = {
            "Low": RiskLevel.LOW,
            "Medium": RiskLevel.MEDIUM,
            "High": RiskLevel.HIGH,
        }

        return ControlResult(
            id=control.id,
            name=control.name,
            category=control.category,
            status=status_map.get(parsed.get("status", "No Evidence"), ControlStatus.NO_EVIDENCE),
            rationale=parsed.get("rationale", ""),
            citations=citations,
            risk_level=risk_map.get(parsed.get("risk_level", "Medium"), RiskLevel.MEDIUM),
            evidence_source=citations[0].document if citations else "No evidence found",
        )

    except Exception as e:
        logger.error(f"Evaluation failed for {control.id}: {e}")
        return ControlResult(
            id=control.id,
            name=control.name,
            category=control.category,
            status=ControlStatus.NO_EVIDENCE,
            rationale=f"Evaluation error: {str(e)}. Please re-run.",
            citations=[],
            risk_level=RiskLevel.HIGH,
            evidence_source="Evaluation error",
        )


async def evaluate_all_controls(
    controls: list[ControlDefinition],
    assessment_id: str,
    vendor_name: str,
    has_documents: bool = False,
) -> list[ControlResult]:
    """Evaluate all controls sequentially."""
    results = []
    for control in controls:
        result = await evaluate_single_control(control, assessment_id, vendor_name, has_documents)
        results.append(result)
    return results
