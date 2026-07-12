"""
Layer 3: Framework Extraction — turns a compliance document into a draft
control framework.

RESPONSIBILITY:
    Takes the raw text of a user-uploaded standard (an internal security
    questionnaire, ISO 27001 excerpt, SIG/CAIQ export, policy checklist)
    and asks the LLM to express it in VendorShield's control schema:
    id, domain, title, description, search_query, what_to_look_for,
    what_good_looks_like, and a four-level scoring_guide per control.

    The output is a DRAFT.  It is returned to the UI for human review
    and editing, and only persisted when the user explicitly saves it
    (POST /api/frameworks) — extraction quality directly drives
    retrieval and scoring quality, so no draft goes live unreviewed.

IMPORTS FROM: config
IMPORTED BY:  routers/controls.py
"""

import json
import logging
import re

from services.llm import complete

logger = logging.getLogger(__name__)

# Documents can be hundreds of pages; the control list is almost always
# expressible from the section headings + requirement statements, so we
# cap what we send to the LLM.
MAX_SOURCE_CHARS = 24_000
MAX_CONTROLS = 40



def slugify(name: str) -> str:
    """Turn a framework name into a filesystem/URL-safe id slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:64] or "custom-framework"


def _build_prompt(source_name: str, text: str) -> str:
    return f"""You are a security compliance expert. The user uploaded a document
("{source_name}") containing a security standard, questionnaire, or control
checklist. Convert it into a machine-usable vendor-assessment framework.

SOURCE DOCUMENT TEXT:
---
{text}
---

Extract the distinct security requirements as controls. Rules:
- Between 5 and {MAX_CONTROLS} controls. Merge near-duplicates; skip boilerplate.
- Group controls into 3 to 6 domains (short category names).
- Give each control a short uppercase id with a domain prefix (e.g. "AC-001").
- "ref" cites where in the source document the requirement came from
  (section number, question id, or clause), or "" if unclear.
- "search_query" is 8-15 keywords/phrases someone would use to FIND evidence
  of this control in a vendor's security documents (for semantic search).
- "what_to_look_for" lists the concrete terms, phrases, and artifacts that
  count as evidence.
- "what_good_looks_like" states the standard the vendor must meet, in 2-4
  sentences.
- "scoring_guide" gives one sentence per outcome describing when to assign it.
- All text fields must be substantive — never empty, never "N/A".

Respond with ONLY this JSON object (no markdown fences, no commentary):
{{
  "name": "short human-readable framework name",
  "description": "1-2 sentence description of what this framework covers",
  "version": "version or year if the document states one, else \\"\\"",
  "controls": [
    {{
      "id": "AC-001",
      "ref": "source section/question reference",
      "domain": "Access Control",
      "title": "short control title",
      "description": "what this control means in plain English (2-3 sentences)",
      "search_query": "keyword phrase list for semantic search",
      "what_to_look_for": "terms and artifacts that count as evidence",
      "what_good_looks_like": "the standard the vendor must meet",
      "scoring_guide": {{
        "pass": "when to score PASS",
        "partial": "when to score PARTIAL",
        "fail": "when to score FAIL",
        "no_evidence": "when to score NO_EVIDENCE"
      }}
    }}
  ]
}}
"""


def _parse_draft(raw: str) -> dict:
    """Parse the LLM's JSON object, tolerating fences and surrounding prose."""
    cleaned = re.sub(r"```json\s*", "", raw)
    cleaned = re.sub(r"```\s*", "", cleaned).strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("controls"), list):
        raise ValueError("LLM response is not a framework object with controls")
    return parsed


def extract_framework_from_text(source_name: str, text: str) -> dict:
    """Draft a control framework from raw document text via the LLM.

    Returns a framework dict shaped like models/frameworks/*.json
    (id, name, description, version, controls) plus extraction metadata.
    Deduplicates control ids and caps the control count; deeper field
    validation happens against FrameworkDefinition when the user saves.

    Raises RuntimeError on LLM or parse failure.
    """
    text = text.strip()
    if len(text) < 200:
        raise RuntimeError(
            "Document text is too short to extract a framework from "
            f"({len(text)} chars) — is the file scanned images or empty?"
        )
    truncated = len(text) > MAX_SOURCE_CHARS
    prompt = _build_prompt(source_name, text[:MAX_SOURCE_CHARS])

    logger.info(
        f"Extracting framework from '{source_name}' "
        f"({len(text)} chars{', truncated' if truncated else ''})"
    )
    try:
        raw = complete(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
            json_mode=True,
        )
        draft = _parse_draft(raw)
    except Exception as e:
        logger.error(f"Framework extraction failed: {e}")
        raise RuntimeError(f"Framework extraction failed: {e}") from e

    # Deduplicate ids and cap count — the LLM occasionally repeats itself
    seen: set[str] = set()
    controls = []
    for c in draft.get("controls", []):
        cid = str(c.get("id", "")).strip()
        if not cid or cid in seen:
            continue
        seen.add(cid)
        controls.append(c)
        if len(controls) >= MAX_CONTROLS:
            break

    name = str(draft.get("name") or source_name).strip()
    framework = {
        "id": slugify(name),
        "name": name,
        "description": str(draft.get("description", "")).strip(),
        "version": str(draft.get("version", "")).strip(),
        "controls": controls,
        # Extraction metadata for the review UI (dropped on save by
        # FrameworkDefinition validation, which ignores unknown fields).
        "source_document": source_name,
        "source_chars_used": min(len(text), MAX_SOURCE_CHARS),
        "source_truncated": truncated,
    }
    logger.info(
        f"Extracted draft framework '{framework['id']}' with {len(controls)} control(s)"
    )
    return framework
