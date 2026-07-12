"""
Layer 3: Follow-up Question Generation — turns assessment gaps into
vendor-facing questions.

RESPONSIBILITY:
    Takes a completed assessment's control results and asks the LLM to
    draft the specific questions a security analyst would send the vendor
    to close each evidence gap.  Only controls whose effective score is
    not PASS produce questions.

    This is the second of three places allowed to call the LLM directly
    (evaluation.py for scoring, chat.py for chat, followup.py for gaps).

IMPORTS FROM: config, models/controls (effective_score)
IMPORTED BY:  routers/assessments.py
"""

import json
import logging
import re

from models.controls import effective_score
from services.llm import complete

logger = logging.getLogger(__name__)



def _build_prompt(vendor_name: str, gapped_controls: list[dict]) -> str:
    """Build the LLM prompt from the controls that did not fully pass."""
    control_lines = []
    for c in gapped_controls:
        control_lines.append(
            f"- control_id: {c.get('control_id')}\n"
            f"  domain: {c.get('domain', '')}\n"
            f"  title: {c.get('title', '')}\n"
            f"  score: {effective_score(c)}\n"
            f"  gap: {c.get('gap') or 'No specific gap described'}"
        )
    controls_text = "\n".join(control_lines)

    return f"""You are a third-party risk analyst preparing a follow-up request
for the vendor "{vendor_name}" after reviewing their security documentation.

For each control below that lacked sufficient evidence, write ONE clear,
professional question to send to the vendor.  Each question must:
- Ask for the SPECIFIC document, policy, or detail that would close the gap
- Be answerable (name concrete artifacts: "your incident response plan",
  "your most recent penetration test summary", "your password policy")
- Be polite but direct — no filler, one sentence, at most two

CONTROLS WITH GAPS:
{controls_text}

Respond with ONLY a JSON array in this exact format (no markdown fences):
[
  {{
    "control_id": "IAM-001",
    "domain": "Identity & Access Management",
    "question": "the question to send to the vendor",
    "rationale": "one short sentence on what evidence this would provide"
  }}
]
"""


def _parse_questions(raw: str) -> list[dict]:
    """Parse the LLM's JSON array, tolerating markdown fences."""
    cleaned = re.sub(r"```json\s*", "", raw)
    cleaned = re.sub(r"```\s*", "", cleaned).strip()
    # Grab the outermost JSON array if the model added prose around it
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)
    parsed = json.loads(cleaned)
    if not isinstance(parsed, list):
        raise ValueError("Expected a JSON array of questions")
    return [
        {
            "control_id": str(q.get("control_id", "")),
            "domain": str(q.get("domain", "")),
            "question": str(q.get("question", "")).strip(),
            "rationale": str(q.get("rationale", "")).strip(),
        }
        for q in parsed
        if q.get("question")
    ]


def generate_follow_up_questions(assessment: dict) -> list[dict]:
    """Generate vendor follow-up questions for every non-passing control.

    Args:
        assessment: A stored assessment record (dict from local_store),
            with vendor_name and control_results.

    Returns:
        List of {control_id, domain, question, rationale} dicts.
        Empty list when every control passed.

    Raises:
        RuntimeError: If the LLM call or parsing fails.
    """
    vendor_name = assessment.get("vendor_name", "the vendor")
    control_results = assessment.get("control_results", [])

    gapped = [c for c in control_results if effective_score(c) != "PASS"]
    if not gapped:
        logger.info("No gapped controls — no follow-up questions needed")
        return []

    prompt = _build_prompt(vendor_name, gapped)

    logger.info(
        f"Generating follow-up questions for {len(gapped)} gapped control(s) "
        f"({vendor_name})"
    )
    try:
        raw = complete(
            [{"role": "user", "content": prompt}],
            temperature=0.2,
            json_mode=True,
        )
        questions = _parse_questions(raw)
    except Exception as e:
        logger.error(f"Follow-up question generation failed: {e}")
        raise RuntimeError(f"Follow-up question generation failed: {e}") from e

    logger.info(f"Generated {len(questions)} follow-up question(s)")
    return questions
