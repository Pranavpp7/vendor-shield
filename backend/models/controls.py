"""
VendorShield Security Control Frameworks — loader and scoring helpers.

Controls are DATA, not code.  Frameworks come from two places:

    models/frameworks/     ← built-in, shipped with the repo
    ├── nist-800-53.json   ← 20 controls, NIST SP 800-53 Rev.5 (default)
    └── soc2-tsc.json      ← 10 controls, SOC 2 Trust Services Criteria

    data/frameworks/       ← user-created (extracted from uploaded docs
                             via POST /api/frameworks/extract, reviewed,
                             then saved).  Deletable; built-ins are not.

Framework JSON shape:
    {
      "id": "nist-800-53",
      "name": "NIST SP 800-53 Rev.5",
      "description": "...",
      "version": "Rev. 5",
      "domain_weights": {"Domain Name": 1.0, ...},
      "controls": [ {control dict}, ... ]
    }

Each control has:
- id: unique identifier within the framework
- ref: the official framework criterion it maps to (aliased to nist_ref
       at load time for backward compatibility with older consumers)
- domain: which assessment category it belongs to
- title / description: what this control means in plain English
- search_query: what we ask the vector DB to find in vendor docs
- what_to_look_for: concepts and phrases the AI should find as evidence
- what_good_looks_like: what the framework actually requires (the standard)
- scoring_guide: how to score Pass / Partial / Fail / No Evidence
- weight: how much this control contributes to the domain score

To add a framework: drop a new JSON file in models/frameworks/ — no code
changes needed.  It appears in list_frameworks() and the API immediately.
"""

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parent.parent

FRAMEWORKS_DIR = Path(__file__).resolve().parent / "frameworks"


def custom_frameworks_dir() -> Path:
    """Directory holding user-created frameworks (under data_dir)."""
    from config import get_settings
    d = _BACKEND_DIR / get_settings().data_dir / "frameworks"
    d.mkdir(parents=True, exist_ok=True)
    return d


DEFAULT_FRAMEWORK_ID = "nist-800-53"


# -------------------------------------------------------------------------
# Framework loading
# -------------------------------------------------------------------------


def _read_framework(path: Path, custom: bool) -> dict | None:
    """Read and normalize one framework JSON file; None if unusable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Skipping unreadable framework file {path.name}: {e}")
        return None
    if not data.get("id") or not data.get("controls"):
        logger.error(f"Skipping malformed framework file {path.name}")
        return None
    for control in data["controls"]:
        control.setdefault("ref", control.get("nist_ref", ""))
        control["nist_ref"] = control["ref"]
    data["custom"] = custom
    return data


@lru_cache()
def _load_frameworks() -> dict[str, dict]:
    """Load every framework JSON file once, keyed by framework id.

    Built-in frameworks (models/frameworks/) load first; user-created
    ones (data/frameworks/) load after and may NOT shadow a built-in id.
    Controls get a "nist_ref" alias of their "ref" field so consumers
    written against the original NIST-only control shape keep working.

    Cache is cleared by save_custom_framework()/delete_custom_framework().
    """
    frameworks: dict[str, dict] = {}
    for path in sorted(FRAMEWORKS_DIR.glob("*.json")):
        data = _read_framework(path, custom=False)
        if data:
            frameworks[data["id"]] = data
    for path in sorted(custom_frameworks_dir().glob("*.json")):
        data = _read_framework(path, custom=True)
        if data is None:
            continue
        if data["id"] in frameworks and not frameworks[data["id"]].get("custom"):
            logger.error(
                f"Custom framework {path.name} shadows built-in id "
                f"'{data['id']}' — skipped"
            )
            continue
        frameworks[data["id"]] = data
    if not frameworks:
        raise RuntimeError(
            f"No control frameworks found in {FRAMEWORKS_DIR} — "
            "at least nist-800-53.json must exist"
        )
    logger.info(f"Loaded {len(frameworks)} control framework(s): {sorted(frameworks)}")
    return frameworks


# -------------------------------------------------------------------------
# Custom framework persistence
# -------------------------------------------------------------------------

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")


def is_builtin_framework(framework_id: str) -> bool:
    fw = _load_frameworks().get(framework_id)
    return bool(fw) and not fw.get("custom", False)


def save_custom_framework(data: dict) -> dict:
    """Persist a user-created framework to data/frameworks/{id}.json.

    The caller (router) is responsible for schema validation; this only
    enforces the id format and the no-shadowing-built-ins rule.
    Saving an existing custom id overwrites it (update semantics).
    """
    fid = str(data.get("id", "")).strip().lower()
    if not _SLUG_RE.match(fid):
        raise ValueError(
            "Framework id must be a lowercase slug (letters, digits, hyphens)"
        )
    if is_builtin_framework(fid):
        raise ValueError(f"'{fid}' is a built-in framework and cannot be replaced")
    data["id"] = fid
    path = custom_frameworks_dir() / f"{fid}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    _load_frameworks.cache_clear()
    logger.info(f"Saved custom framework '{fid}' ({len(data.get('controls', []))} controls)")
    return get_framework(fid)


def delete_custom_framework(framework_id: str) -> bool:
    """Delete a user-created framework.  Built-ins raise ValueError."""
    fw = _load_frameworks().get(framework_id)
    if fw is None:
        return False
    if not fw.get("custom", False):
        raise ValueError(f"'{framework_id}' is built-in and cannot be deleted")
    path = custom_frameworks_dir() / f"{framework_id}.json"
    path.unlink(missing_ok=True)
    _load_frameworks.cache_clear()
    logger.info(f"Deleted custom framework '{framework_id}'")
    return True


def resolve_framework_id(framework_id: str | None) -> str:
    """Normalize a framework id, falling back to the default.

    Raises KeyError with a helpful message for unknown ids so callers
    (routers, MCP tools) surface a clear error instead of a silent default.
    """
    fid = (framework_id or "").strip() or DEFAULT_FRAMEWORK_ID
    if fid not in _load_frameworks():
        raise KeyError(
            f"Unknown framework '{fid}'. Available: {sorted(_load_frameworks())}"
        )
    return fid


def get_framework(framework_id: str | None = None) -> dict:
    """Return the full framework dict (metadata + controls)."""
    return _load_frameworks()[resolve_framework_id(framework_id)]


def list_frameworks() -> list[dict]:
    """Return summary metadata for every available framework."""
    out = []
    for fw in _load_frameworks().values():
        out.append({
            "id": fw["id"],
            "name": fw.get("name", fw["id"]),
            "description": fw.get("description", ""),
            "version": fw.get("version", ""),
            "control_count": len(fw["controls"]),
            "domains": _domains_of(fw),
            "custom": fw.get("custom", False),
        })
    return out


def _domains_of(framework: dict) -> list[str]:
    seen: list[str] = []
    for c in framework["controls"]:
        if c["domain"] not in seen:
            seen.append(c["domain"])
    return seen


# -------------------------------------------------------------------------
# Control accessors (framework-aware; default to NIST for backward compat)
# -------------------------------------------------------------------------


def get_all_controls(framework_id: str | None = None) -> list[dict]:
    """Return all controls of a framework (default: NIST SP 800-53)."""
    return get_framework(framework_id)["controls"]


def get_controls_by_domain(domain: str, framework_id: str | None = None) -> list[dict]:
    """Return controls filtered by domain name."""
    return [c for c in get_all_controls(framework_id) if c["domain"] == domain]


def get_domains(framework_id: str | None = None) -> list[str]:
    """Return the list of unique domains, in framework order."""
    return _domains_of(get_framework(framework_id))


# -------------------------------------------------------------------------
# Scoring prompt
# -------------------------------------------------------------------------


def get_scoring_prompt(control: dict, retrieved_chunks: list[str]) -> str:
    """
    Build the prompt we send to the LLM for scoring a control.
    This is the instruction that tells the LLM exactly how to judge.

    retrieved_chunks: list of paragraphs found by the vector search
    """
    chunks_text = "\n\n---\n\n".join(
        [f"[Chunk {i+1}]\n{chunk}" for i, chunk in enumerate(retrieved_chunks)]
    )

    ref = control.get("ref") or control.get("nist_ref", "")

    return f"""You are a security auditor conducting a vendor risk assessment.

CONTROL BEING ASSESSED:
Control ID: {control['id']}
Framework Reference: {ref}
Control Title: {control['title']}
Control Description: {control['description']}

WHAT GOOD LOOKS LIKE (the standard):
{control['what_good_looks_like']}

RETRIEVED EVIDENCE FROM VENDOR DOCUMENTS:
{chunks_text}

WHAT TO LOOK FOR:
{control.get('what_to_look_for', 'Evidence relevant to the control description above.')}

SCORING INSTRUCTIONS:
Based ONLY on the evidence above from the vendor's own documents, score this control.
Do NOT use any knowledge outside of these documents.

ATTRIBUTION RULE (critical — check this BEFORE scoring):
Evidence only counts if it is the VENDOR asserting something about ITS OWN
practices, systems, or policies ("we encrypt...", "our SOC monitors...",
"the platform enforces...").  Do NOT credit:
- Generic how-to or best-practice guidance addressed to the reader
  ("you should enable MFA", "configure alerts in your SIEM")
- Lists of example products or vendors ("SIEM options: Datadog, Splunk,
  SolarWinds") — naming tools the READER might use is not a claim that the
  vendor uses them
- Descriptions of industry standards, threat landscapes, or what
  organizations in general do
Vendor documents often include educational/marketing content written FOR
customers; treating that as the vendor's self-attestation fabricates claims
the vendor never made.  If the only relevant text is generic guidance,
score NO_EVIDENCE and state in "reasoning" that the documents contain
guidance about the topic but never state the vendor's own practice.

Score definitions:
- PASS: Clear, specific evidence that the vendor meets this control
- PARTIAL: Some evidence exists but it is vague, incomplete, or only partially meets the standard
- FAIL: The documents contain evidence that the vendor does NOT meet this control
- NO_EVIDENCE: The documents contain no relevant information about this control

Write like an auditor preparing a workpaper that a security reviewer will rely on:
- "evidence_quote" must be a VERBATIM quote copied exactly from one of the
  chunks above (the single strongest passage). Never paraphrase. null only
  when truly nothing relevant exists.
- "reasoning" must be 2-4 sentences: state what the evidence says, how it
  compares to the standard in "what good looks like", and what (if anything)
  falls short. Name specifics (mechanisms, frequencies, scopes) — never write
  generic filler like "the vendor addresses this control".
- If NO_EVIDENCE: in "reasoning", name the specific topics you searched the
  chunks for (e.g. "no mention of MFA, one-time passwords, hardware tokens,
  or any second authentication factor") so a human can trust the negative
  finding without re-reading the documents.
- "gap" must be actionable: what document, policy detail, or artifact the
  vendor should provide to close it.

Respond in this exact JSON format:
{{
  "control_id": "{control['id']}",
  "score": "PASS|PARTIAL|FAIL|NO_EVIDENCE",
  "confidence": 0.85,
  "evidence_quote": "verbatim quote from the chunks above, or null if NO_EVIDENCE",
  "evidence_chunk": 1,
  "reasoning": "2-4 auditor-grade sentences as specified above",
  "gap": "what is missing or needs improvement, or null if PASS"
}}

confidence is a float from 0.0 to 1.0:
  1.0 — a specific, unambiguous quote directly proves the score
  0.75 — clear supporting evidence with minor gaps
  0.5  — some relevant evidence but substantial ambiguity
  0.25 — very thin evidence; mostly inferring
  0.0  — no relevant evidence found; pure guess
"""


# -------------------------------------------------------------------------
# Score calculation
# -------------------------------------------------------------------------

# Values for VERIFIED findings only.  NO_EVIDENCE is deliberately absent:
# "the documents don't mention this" is a documentation gap (reported as
# reduced coverage), NOT a confirmed deficiency (that's FAIL, worth 0.0).
SCORE_MAP = {"PASS": 1.0, "PARTIAL": 0.5, "FAIL": 0.0, "NO_EVIDENCE": 0.0}

_UNVERIFIED = "NO_EVIDENCE"


def effective_score(result: dict) -> str:
    """The score that counts: the analyst's override when present, else the AI's.

    Supports both raw LLM result dicts and stored control_result dicts.
    """
    return result.get("analyst_score") or result.get("score", "NO_EVIDENCE")


def calculate_scores(
    control_results: list[dict],
    framework_id: str | None = None,
) -> dict:
    """
    Given a list of scored controls, calculate domain and overall scores.

    SCORING SEMANTICS (coverage-adjusted):
        The score answers "of what we could verify, how good is it?"
        - PASS=1.0, PARTIAL=0.5, FAIL=0.0 count toward the score.
        - NO_EVIDENCE and unevaluated controls are EXCLUDED from every
          denominator: an absent document is an unknown, not a failure.
          Punishing unknowns as failures conflates "we couldn't check"
          with "we checked and it's bad" — a well-certified vendor
          assessed from thin public docs would otherwise score like a
          genuinely deficient one.
        - The unknown surface is reported separately as `coverage`
          (percent of framework controls with verifiable findings).
          Consumers MUST show coverage next to the score; a 90/100 at
          30% coverage is a very different statement than at 100%.

    control_results format:
    [{"control_id": "IAM-001", "score": "PASS", ...}, ...]
    When a result carries an "analyst_score" (human override), it takes
    precedence over the AI "score" — overriding NO_EVIDENCE to a real
    verdict moves that control INTO the scored set (raises coverage).
    """
    results_by_id = {r["control_id"]: r for r in control_results}

    domain_scores = {}
    verified_vals: list[float] = []
    total_controls = 0

    for domain in get_domains(framework_id):
        domain_controls = get_controls_by_domain(domain, framework_id)
        total_controls += len(domain_controls)
        domain_vals: list[float] = []

        for control in domain_controls:
            result = results_by_id.get(control["id"])
            if result is None:
                continue  # never evaluated → unknown, not a failure
            score = effective_score(result)
            if score == _UNVERIFIED:
                continue  # documentation gap → coverage, not score
            domain_vals.append(SCORE_MAP.get(score, 0.0))

        verified_vals.extend(domain_vals)
        # A domain with nothing verifiable scores 0 — the control-level
        # counts (all "no evidence") make the reason visible in the UI.
        domain_scores[domain] = (
            round(sum(domain_vals) / len(domain_vals) * 100) if domain_vals else 0
        )

    overall = (
        round(sum(verified_vals) / len(verified_vals) * 100) if verified_vals else 0
    )
    coverage = (
        round(len(verified_vals) / total_controls * 100) if total_controls else 0
    )

    if overall >= 70:
        risk_level = "Low"
    elif overall >= 40:
        risk_level = "Medium"
    else:
        risk_level = "High"

    return {
        "overall_score": overall,
        "risk_level": risk_level,
        "domain_scores": domain_scores,
        "coverage": coverage,
        "verified_controls": len(verified_vals),
        "total_controls": total_controls,
    }
