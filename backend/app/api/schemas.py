"""Pydantic request and response schemas for Hindsight Cloud API operations."""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


# --- Retain Schemas ---

class RetainItem(BaseModel):
    """An individual memory item to retain in Hindsight."""

    content: str = Field(..., min_length=1, description="Natural language content to store.")
    context: Optional[str] = Field(default=None, description="Optional context or origin (e.g. incident_report).")
    timestamp: Optional[str] = Field(default=None, description="Optional ISO-8601 timestamp.")

    model_config = ConfigDict(extra="ignore")


class RetainRequest(BaseModel):
    """Request payload for retaining memories in a bank."""

    items: list[RetainItem] = Field(..., min_length=1, description="List of memory items to retain.")
    async_mode: bool = Field(default=False, alias="async", description="Whether to process asynchronously.")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class TokenUsage(BaseModel):
    """Token usage metrics reported by Hindsight Cloud."""

    input_tokens: Optional[int] = Field(default=None, description="Input tokens consumed.")
    output_tokens: Optional[int] = Field(default=None, description="Output tokens generated.")
    total_tokens: Optional[int] = Field(default=None, description="Total tokens consumed.")

    model_config = ConfigDict(extra="ignore")


class RetainResponse(BaseModel):
    """Response payload returned after retaining memories."""

    success: bool = Field(..., description="Whether retention succeeded.")
    bank_id: str = Field(..., description="Target bank identifier.")
    items_count: int = Field(..., description="Number of items processed.")
    async_mode: bool = Field(default=False, alias="async", description="Whether processing was async.")
    operation_id: Optional[str] = Field(default=None, description="Operation ID if processed async.")
    usage: Optional[TokenUsage] = Field(default=None, description="Token usage details.")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


# --- Recall Schemas ---

class RecallRequest(BaseModel):
    """Request payload for searching memories in a bank."""

    query: str = Field(..., min_length=1, description="Natural language search query.")
    types: Optional[list[str]] = Field(default=None, description="Filter by memory types (world, observation, experience).")
    budget: Optional[str] = Field(default=None, description="Search budget level (low, mid, high).")
    max_tokens: Optional[int] = Field(default=None, ge=1, description="Maximum tokens to return.")
    trace: Optional[bool] = Field(default=False, description="Enable debug retrieval trace.")
    query_timestamp: Optional[str] = Field(default=None, description="Reference ISO-8601 timestamp for temporal queries.")

    model_config = ConfigDict(extra="ignore")


class MemoryResult(BaseModel):
    """An individual memory retrieved from Hindsight."""

    id: str = Field(..., description="Unique memory ID.")
    text: str = Field(..., description="Content of the memory.")
    type: Optional[str] = Field(default=None, description="Memory type classification.")
    entities: Optional[list[str]] = Field(default=None, description="Entities referenced in memory.")
    context: Optional[str] = Field(default=None, description="Context associated with memory.")
    mentioned_at: Optional[str] = Field(default=None, description="Timestamp associated with memory.")

    model_config = ConfigDict(extra="ignore")


class RecallResponse(BaseModel):
    """Response payload returned when recalling memories."""

    results: list[MemoryResult] = Field(default_factory=list, description="Retrieved memories.")
    entities: Optional[dict[str, Any]] = Field(default=None, description="Associated entity metadata.")

    model_config = ConfigDict(extra="ignore")


# --- Incident Intake Schemas ---

class IncidentSeverity(str, Enum):
    """Normalized incident severity level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentCreateRequest(BaseModel):
    """Payload to create and intake a new incident."""

    title: str = Field(..., min_length=1, max_length=255, description="Incident title or summary.")
    description: str = Field(..., min_length=1, description="Detailed explanation of the incident.")
    affected_service: str = Field(..., min_length=1, max_length=100, description="Affected service or component.")
    severity: IncidentSeverity = Field(..., description="Severity level: low, medium, high, critical.")
    logs: Optional[str] = Field(default=None, description="Optional log traces or diagnostic output.")

    model_config = ConfigDict(extra="ignore")

    @field_validator("title", "description", "affected_service", mode="before")
    @classmethod
    def strip_and_validate_non_empty(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Field cannot be empty or whitespace only.")
        return v

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip().lower()
        return v

    @field_validator("logs", mode="before")
    @classmethod
    def process_logs(cls, v: Any) -> Optional[str]:
        if isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v


class IncidentResponse(BaseModel):
    """Response payload for an incident record."""

    id: str = Field(..., description="Unique incident identifier.")
    title: str = Field(..., description="Incident title.")
    description: str = Field(..., description="Detailed description.")
    affected_service: str = Field(..., description="Affected service.")
    severity: IncidentSeverity = Field(..., description="Incident severity.")
    logs: Optional[str] = Field(default=None, description="Diagnostic logs.")
    status: str = Field(default="open", description="Incident status.")
    created_at: str = Field(..., description="Timezone-aware UTC timestamp of creation.")
    updated_at: Optional[str] = Field(default=None, description="Timezone-aware UTC timestamp of last update.")

    model_config = ConfigDict(extra="ignore")


class IncidentListResponse(BaseModel):
    """Paginated list of incident records."""

    items: list[IncidentResponse] = Field(default_factory=list, description="List of incidents.")
    total: int = Field(..., ge=0, description="Total number of incidents matching filter.")
    limit: int = Field(..., ge=1, description="Page limit applied.")
    offset: int = Field(..., ge=0, description="Offset index applied.")

    model_config = ConfigDict(extra="ignore")


# --- Incident Analysis Schemas ---

class ExtractedSymptoms(BaseModel):
    """Structured symptoms deterministically extracted from incident details."""

    affected_service: str = Field(..., description="Affected service name.")
    severity: str = Field(..., description="Incident severity level.")
    indicators: list[str] = Field(default_factory=list, description="Deduplicated indicators from symptoms and logs.")
    recall_query: str = Field(..., description="Search query derived for Hindsight recall.")

    model_config = ConfigDict(extra="ignore")


class AnalysisSuggestion(BaseModel):
    """An evidence-based or general diagnostic suggestion."""

    category: str = Field(..., description="Category: historical_resolution, historical_observation, diagnostic_step, or precaution.")
    suggestion: str = Field(..., description="Actionable suggestion or check to perform.")
    evidence_source: Optional[str] = Field(
        default=None,
        description="Source of evidence (e.g. 'memory:<id>', 'safety_guideline', or 'general_triage').",
    )

    model_config = ConfigDict(extra="ignore")


class IncidentAnalysisRequest(BaseModel):
    """Optional parameters for the incident analysis request."""

    query_override: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional custom query overriding automatic symptom extraction for recall.",
    )
    max_tokens: Optional[int] = Field(
        default=None,
        ge=1,
        le=4000,
        description="Optional maximum tokens to return from Hindsight recall.",
    )

    model_config = ConfigDict(extra="ignore")

    @field_validator("query_override", mode="before")
    @classmethod
    def clean_query_override(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v


class IncidentAnalysisResponse(BaseModel):
    """Structured analysis report for an incident."""

    incident_id: str = Field(..., description="Unique incident identifier.")
    analyzed_at: str = Field(..., description="Timezone-aware UTC timestamp when analysis was generated.")
    bank_id: str = Field(..., description="Hindsight memory bank queried.")
    incident_title: str = Field(..., description="Title of the incident.")
    extracted_symptoms: ExtractedSymptoms = Field(..., description="Structured symptoms identified.")
    recalled_memories: list[MemoryResult] = Field(default_factory=list, description="Memories retrieved from Hindsight.")
    suggestions: list[AnalysisSuggestion] = Field(default_factory=list, description="Evidence-based and diagnostic suggestions.")
    has_historical_matches: bool = Field(..., description="True if any relevant memories were found in Hindsight.")

    model_config = ConfigDict(extra="ignore")


# --- Incident Outcome & Learning Schemas ---

class IncidentOutcomeStatus(str, Enum):
    """Normalized status of an incident resolution outcome."""

    SUCCESS = "success"
    FAILURE = "failure"


class IncidentOutcomeRequest(BaseModel):
    """Request payload to record an engineer's incident resolution outcome."""

    incident_id: Optional[str] = Field(
        default=None,
        description="Optional incident ID matching the path parameter.",
    )
    resolution_attempted: str = Field(
        ...,
        min_length=1,
        description="Description of the resolution action attempted by the engineer.",
    )
    outcome: IncidentOutcomeStatus = Field(
        ...,
        description="Outcome of the resolution attempt ('success' or 'failure').",
    )
    engineer_notes: Optional[str] = Field(
        default=None,
        description="Optional diagnostic or post-resolution notes.",
    )

    model_config = ConfigDict(extra="ignore")

    @field_validator("resolution_attempted", mode="before")
    @classmethod
    def validate_resolution(cls, v: Any) -> str:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("resolution_attempted cannot be empty or whitespace only.")
            return v
        raise ValueError("resolution_attempted must be a string.")

    @field_validator("outcome", mode="before")
    @classmethod
    def normalize_outcome(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip().lower()
        return v

    @field_validator("engineer_notes", mode="before")
    @classmethod
    def clean_engineer_notes(cls, v: Any) -> Optional[str]:
        if isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v


class IncidentOutcomeRecord(BaseModel):
    """Local SQLite record of an incident outcome."""

    id: str = Field(..., description="Unique outcome record ID.")
    incident_id: str = Field(..., description="Associated incident ID.")
    resolution_attempted: str = Field(..., description="Action attempted.")
    outcome: IncidentOutcomeStatus = Field(..., description="Outcome status.")
    engineer_notes: Optional[str] = Field(default=None, description="Engineer notes.")
    created_at: str = Field(..., description="Timezone-aware UTC timestamp of outcome record.")

    model_config = ConfigDict(extra="ignore")


class IncidentOutcomeResponse(BaseModel):
    """Response returned after recording an incident outcome."""

    outcome: IncidentOutcomeRecord = Field(..., description="Recorded outcome record.")
    hindsight_retained: bool = Field(..., description="Whether retention in Hindsight memory bank succeeded.")
    bank_id: str = Field(..., description="Hindsight memory bank identifier.")

    model_config = ConfigDict(extra="ignore")
