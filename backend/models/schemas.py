"""Pydantic models for API requests and responses."""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# --- Enums ---

class ControlStatus(str, Enum):
    PASS = "Pass"
    PARTIAL = "Partial"
    FAIL = "Fail"
    NO_EVIDENCE = "No Evidence"


class RiskLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


# --- Control Models ---

class ControlDefinition(BaseModel):
    id: str
    name: str
    category: str
    description: str = ""
    weight: float = 1.0


class Citation(BaseModel):
    document: str
    page: Optional[int] = None
    excerpt: str = ""
    similarity: Optional[float] = None


class ControlResult(BaseModel):
    id: str
    name: str
    category: str
    status: ControlStatus
    rationale: str = ""
    citations: list[Citation] = []
    risk_level: RiskLevel = RiskLevel.MEDIUM
    evidence_source: str = "No evidence found"


class DomainScore(BaseModel):
    domain: str
    score: float
    total_controls: int
    passed: int
    partial: int
    failed: int
    no_evidence: int


# --- Request Models ---

class DocumentUploadRequest(BaseModel):
    assessment_id: str
    vendor_name: str
    document_id: Optional[str] = None


class URLIngestRequest(BaseModel):
    url: str
    assessment_id: str
    vendor_name: str


class AssessmentRunRequest(BaseModel):
    vendor_name: str
    assessment_id: str
    controls: Optional[list[ControlDefinition]] = None  # override default controls


class ChatRequest(BaseModel):
    question: str
    assessment_id: str
    context: Optional[str] = None


class SummaryRequest(BaseModel):
    vendor_name: str
    assessment_id: str
    score: int
    risk_level: str
    controls: list[dict]
    notes: str = ""


# --- Response Models ---

class DocumentUploadResponse(BaseModel):
    document_id: str
    chunks_created: int
    embeddings_generated: bool
    status: str


class AssessmentResponse(BaseModel):
    assessment_id: str
    vendor_name: str
    overall_score: int
    risk_level: RiskLevel
    domain_scores: list[DomainScore]
    control_results: list[ControlResult]
    summary: str
    gaps_summary: str


class ChatResponse(BaseModel):
    reply: str
    sources: list[Citation] = []


class SummaryResponse(BaseModel):
    summary: str


class ControlsListResponse(BaseModel):
    controls: list[ControlDefinition]
    categories: list[str]
