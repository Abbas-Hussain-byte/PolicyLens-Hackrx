"""Pydantic request/response models for the API."""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime


# ─── Enums ───────────────────────────────────────────────────────────

class QueryTier(str, Enum):
    FAST_INFO = "fast_info"
    GROUNDED_QA = "grounded_qa"
    VERIFIED = "verified"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReadingLevel(str, Enum):
    SIMPLE = "simple"
    STANDARD = "standard"
    EXPERT = "expert"


# ─── Source / Evidence ───────────────────────────────────────────────

class SourceClause(BaseModel):
    """A grounded source clause from the policy document."""
    section_title: str = ""
    page_number: int = 0
    text: str = ""
    relevance_score: float = 0.0


class ConfidenceScore(BaseModel):
    """Confidence assessment for an answer."""
    retrieval_score: float = Field(0.0, ge=0.0, le=1.0)
    coverage_score: float = Field(0.0, ge=0.0, le=1.0)
    llm_confidence: float = Field(0.0, ge=0.0, le=1.0)

    @property
    def overall(self) -> float:
        return round(
            0.3 * self.retrieval_score
            + 0.3 * self.coverage_score
            + 0.4 * self.llm_confidence,
            3,
        )

    @property
    def level(self) -> ConfidenceLevel:
        score = self.overall
        if score >= 0.75:
            return ConfidenceLevel.HIGH
        if score >= 0.45:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW


# ─── Policy ──────────────────────────────────────────────────────────

class PolicyUploadResponse(BaseModel):
    policy_id: str
    filename: str
    page_count: int
    chunk_count: int
    summary: str = ""
    status: str = "processed"


class PolicyInfo(BaseModel):
    policy_id: str
    filename: str
    page_count: int
    chunk_count: int
    uploaded_at: str
    summary: str = ""


class PolicyListResponse(BaseModel):
    policies: list[PolicyInfo]
    total: int


# ─── Query / Answer ─────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    policy_id: str
    reading_level: ReadingLevel = ReadingLevel.STANDARD
    language: str = "en"


class AmbiguityInfo(BaseModel):
    found: bool = False
    details: list[str] = []
    risk_level: str = "low"


class ContradictionInfo(BaseModel):
    found: bool = False
    details: list[str] = []


class QueryResponse(BaseModel):
    answer: str
    tier: QueryTier
    confidence: ConfidenceScore
    sources: list[SourceClause] = []
    ambiguity: Optional[AmbiguityInfo] = None
    contradiction: Optional[ContradictionInfo] = None
    verification_status: Optional[str] = None
    reading_level: ReadingLevel = ReadingLevel.STANDARD
    language: str = "en"
    latency_ms: int = 0


# ─── Eligibility ─────────────────────────────────────────────────────

class EligibilityRequest(BaseModel):
    policy_id: str
    condition: str
    details: str = ""
    language: str = "en"


class EligibilityResponse(BaseModel):
    eligible: Optional[bool] = None
    explanation: str
    conditions: list[str] = []
    waiting_period: str = ""
    confidence: ConfidenceScore
    sources: list[SourceClause] = []
    disclaimer: str = "This is an AI assessment. Please consult your insurer for confirmation."


# ─── Exclusions ───────────────────────────────────────────────────────

class ExclusionItem(BaseModel):
    title: str
    description: str
    section: str = ""
    page: int = 0
    risk_note: str = ""


class ExclusionsResponse(BaseModel):
    exclusions: list[ExclusionItem] = []
    total: int = 0
    confidence: ConfidenceScore
    sources: list[SourceClause] = []


# ─── Comparison ───────────────────────────────────────────────────────

class CompareRequest(BaseModel):
    policy_ids: list[str] = Field(..., min_length=2, max_length=4)
    aspects: list[str] = ["coverage", "exclusions", "premiums", "waiting_period", "claim_process"]
    language: str = "en"


class ComparisonAspect(BaseModel):
    aspect: str
    policies: dict[str, str] = {}  # policy_id -> finding
    recommendation: str = ""


class CompareResponse(BaseModel):
    comparisons: list[ComparisonAspect] = []
    overall_recommendation: str = ""
    confidence: ConfidenceScore
    sources: dict[str, list[SourceClause]] = {}


# ─── Batch ────────────────────────────────────────────────────────────

class BatchQueryItem(BaseModel):
    question: str
    policy_id: str


class BatchRequest(BaseModel):
    queries: list[BatchQueryItem]
    reading_level: ReadingLevel = ReadingLevel.STANDARD


class BatchResponse(BaseModel):
    results: list[QueryResponse]
    total: int
    processed: int
    failed: int = 0


# ─── Health ───────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    gemini_connected: bool = False
    policies_loaded: int = 0
    embedding_model: str = ""
