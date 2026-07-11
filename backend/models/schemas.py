"""
Layer 2: Pydantic request/response models for the API.

RESPONSIBILITY:
    Defines the data shapes for all HTTP requests and responses.
    These models validate incoming data and serialize outgoing data.
    They do NOT contain business logic.

    Note: Security controls are plain Python dicts defined in
    models/controls.py — they do NOT have their own Pydantic model.
    This is intentional: controls.py is the single source of truth
    and must not be modified.

IMPORTS FROM: nothing
IMPORTED BY:  routers, services (for type hints), chains
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum


# --- Enums ---

class ControlScore(str, Enum):
    """Possible scores for a single control evaluation.

    These values match exactly what the LLM returns in its JSON output
    and what calculate_scores() in controls.py expects.
    Old name was ControlStatus with values like "Pass" — now uppercase
    to match the LLM prompt in get_scoring_prompt().
    """
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"
    NO_EVIDENCE = "NO_EVIDENCE"


class RiskLevel(str, Enum):
    """Overall risk level for a vendor assessment.

    Computed by calculate_scores() in controls.py:
    - Low:    overall score >= 70
    - Medium: overall score >= 40
    - High:   overall score < 40
    """
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


# --- Evidence & Citations ---

class Citation(BaseModel):
    """A reference to a specific location in an uploaded document.

    Used by retrieval.py to track which document chunks were used
    as evidence during evaluation.
    """
    document: str                       # filename or URL
    page: Optional[int] = None          # page number (if PDF)
    excerpt: str = ""                   # short text snippet
    similarity: Optional[float] = None  # cosine similarity score


# --- Control Evaluation Result ---

class ControlResult(BaseModel):
    """Result of evaluating a single security control against vendor documents.

    Fields control_id, score, confidence, evidence_quote, evidence_chunk,
    reasoning, and gap come directly from the LLM's JSON response
    (see get_scoring_prompt() in controls.py for the exact format).

    Fields domain, title, and citations are added by evaluation.py
    for display purposes.
    """
    control_id: str                         # e.g. "IAM-001"
    score: ControlScore                     # PASS / PARTIAL / FAIL / NO_EVIDENCE
    confidence: float = 0.5                 # 0.0 (guessing) → 1.0 (certain)
    evidence_quote: Optional[str] = None    # exact quote from vendor docs, or null
    evidence_chunk: Optional[int] = None    # which retrieved chunk had the evidence
    reasoning: str = ""                     # 1-2 sentence explanation
    gap: Optional[str] = None              # what's missing, or null if PASS
    # Metadata added by evaluation.py (not from LLM):
    domain: str = ""                        # which domain this control belongs to
    title: str = ""                         # short name of the control
    citations: list[Citation] = []          # source documents used for retrieval
    # Human-in-the-loop override (set via the override endpoint, never by the LLM).
    # When analyst_score is set it supersedes `score` in all aggregations;
    # `score` always preserves the original AI verdict for the audit trail.
    analyst_score: Optional[ControlScore] = None
    analyst_comment: Optional[str] = None
    overridden_by: Optional[str] = None     # user_id of the analyst ("" in dev mode)
    overridden_at: Optional[str] = None     # ISO-8601 UTC timestamp


# --- Request Models ---

class URLIngestRequest(BaseModel):
    """Request to ingest a URL's content into the vector database."""
    url: str
    assessment_id: str
    vendor_name: str
    # "vendor" = vendor-authored evidence; "reference" = generic guidance
    # (down-weighted in retrieval, labeled for the LLM judge)
    doc_type: Literal["vendor", "reference"] = "vendor"


class AssessmentRunRequest(BaseModel):
    """Request to run a full vendor risk assessment."""
    vendor_name: str
    assessment_id: str
    framework_id: str = "nist-800-53"       # which control framework to assess against


class ControlOverrideRequest(BaseModel):
    """Analyst override of an AI-assigned control score.

    score = null clears an existing override (reverts to the AI score).
    """
    score: Optional[ControlScore] = None
    comment: str = ""


class ScoringGuide(BaseModel):
    """Per-score guidance the LLM uses when judging a control."""
    pass_: str = Field(..., alias="pass", min_length=5)
    partial: str = Field(..., min_length=5)
    fail: str = Field(..., min_length=5)
    no_evidence: str = Field(..., min_length=5)

    model_config = {"populate_by_name": True}


class FrameworkControlDef(BaseModel):
    """One control inside a (custom) framework definition.

    Every field feeds the assessment pipeline: search_query drives
    retrieval, the what_* fields and scoring_guide drive the LLM's
    judgment — hence the minimum lengths, which reject empty LLM output.
    """
    id: str = Field(..., pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{1,31}$")
    ref: str = ""
    domain: str = Field(..., min_length=3, max_length=60)
    title: str = Field(..., min_length=5, max_length=120)
    description: str = Field(..., min_length=20)
    search_query: str = Field(..., min_length=10)
    what_to_look_for: str = Field(..., min_length=20)
    what_good_looks_like: str = Field(..., min_length=20)
    scoring_guide: ScoringGuide
    weight: float = 1


class FrameworkDefinition(BaseModel):
    """A full control framework, as stored in data/frameworks/{id}.json."""
    id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    name: str = Field(..., min_length=3, max_length=120)
    description: str = ""
    version: str = ""
    controls: list[FrameworkControlDef] = Field(..., min_length=1, max_length=60)


class RiskProfileRequest(BaseModel):
    """Inherent-risk intake profile for a vendor relationship.

    Answers describe the relationship BEFORE any controls are considered:
    what data the vendor touches, how critical they are to the business,
    and how deeply they reach into our systems.
    """
    data_sensitivity: Literal["low", "moderate", "high"]
    business_criticality: Literal["low", "moderate", "high"]
    access_scope: Literal["low", "moderate", "high"]


class ChatRequest(BaseModel):
    """Request to chat about vendor documents."""
    question: str
    assessment_id: str
    context: Optional[str] = None


class SummaryRequest(BaseModel):
    """Request to generate an executive summary."""
    vendor_name: str
    assessment_id: str
    score: int
    risk_level: str
    controls: list[dict]
    notes: str = ""


# --- Response Models ---

class DocumentUploadResponse(BaseModel):
    """Response after uploading and ingesting a document."""
    document_id: str
    chunks_created: int
    embeddings_generated: bool
    status: str
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    source_url: Optional[str] = None


class AssessmentResponse(BaseModel):
    """Full assessment result returned after running all 20 controls.

    domain_scores is a dict mapping domain name to percentage (0-100),
    matching the output format of calculate_scores() in controls.py.
    Example: {"Identity & Access Management": 80, "Data Protection": 60}
    """
    assessment_id: str
    vendor_name: str
    overall_score: int                          # 0-100
    risk_level: RiskLevel                       # Low / Medium / High
    domain_scores: dict[str, int]               # domain name -> percentage
    control_results: list[ControlResult]        # all scored controls
    gaps_summary: str = ""                      # markdown summary of gaps
    summary: str = ""                           # LLM-generated executive summary
    created_at: str = ""                        # ISO-8601 UTC timestamp of assessment run
    framework_id: str = "nist-800-53"           # framework the controls came from
    # Evidence coverage: % of framework controls with a VERIFIED finding
    # (PASS/PARTIAL/FAIL).  The headline overall_score counts unverified
    # controls as 0 (unaccepted risk); verified_score is the average over
    # verified controls only — display both next to the headline.
    coverage: Optional[int] = None
    verified_score: Optional[int] = None
    verified_controls: Optional[int] = None
    total_controls: Optional[int] = None


class ChatResponse(BaseModel):
    """Response from the chat endpoint."""
    reply: str
    sources: list[Citation] = []


class SummaryResponse(BaseModel):
    """Response from the summary generation endpoint."""
    summary: str


class ControlsListResponse(BaseModel):
    """Response listing all available security controls.

    controls is a list of raw dicts from controls.py — not Pydantic models.
    domains is the list of 4 domain names from get_domains().
    """
    controls: list[dict]    # raw control dicts from controls.py
    domains: list[str]      # the 4 domain names
