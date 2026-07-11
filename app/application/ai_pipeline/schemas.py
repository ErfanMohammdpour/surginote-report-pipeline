"""Pydantic contracts for AI pipeline agents."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ALLOWED_MARKER_TYPES = frozenset({"comment", "warning", "audio", "event"})


class PhaseInput(BaseModel):
    id: str
    order: int | None = None
    name: str
    shortName: str | None = None
    description: str | None = None
    color: str | None = None
    startTime: float | None = None
    endTime: float | None = None
    phacoMethod: str | None = None
    source: str | None = None


class MetricInput(BaseModel):
    id: str
    name: str
    maxScore: float | None = Field(default=5.0, ge=0)


class MarkerInput(BaseModel):
    id: str
    type: str
    timestamp: float
    label: str | None = None
    text: str | None = None
    color: str | None = None
    createdAt: str | None = None

    @field_validator("type")
    @classmethod
    def _validate_marker_type(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        if normalized not in ALLOWED_MARKER_TYPES:
            allowed = ", ".join(sorted(ALLOWED_MARKER_TYPES))
            raise ValueError(f"marker type must be one of: {allowed}")
        return normalized


class AnnotationPayload(BaseModel):
    phases: list[PhaseInput] = Field(min_length=1)
    metrics: dict[str, list[MetricInput]] = Field(default_factory=dict)
    scores: dict[str, dict[str, float]] = Field(default_factory=dict)
    markers: list[MarkerInput] = Field(default_factory=list)
    version: int | None = None
    savedAt: str | None = None


class GenerateSettings(BaseModel):
    tone: int = Field(default=2, ge=0, le=4)
    emphasis: list[str] = Field(default_factory=lambda: ["technical", "safety"])
    locale: Literal["en", "fa"] = "en"


class AIConfig(BaseModel):
    provider: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    enable_review: bool | None = None
    enable_cache: bool | None = None
    parallel_phases: bool | None = None
    max_tokens: int | None = Field(default=None, ge=1)


class NormalizedData(BaseModel):
    normalized_phases: list[PhaseInput]
    normalized_markers: list[MarkerInput]
    metrics: dict[str, list[MetricInput]]
    scores: dict[str, dict[str, float]]
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractorErrorOutput(BaseModel):
    error: str
    normalized: None = None


class PhaseAnalysisOutput(BaseModel):
    phase_id: str
    clinical_narrative: str = Field(min_length=1)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    key_insights: list[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0, le=1)


class MarkersAnalysisOutput(BaseModel):
    commentary_insights: list[str] = Field(default_factory=list)
    emotion_trend: Literal["positive", "negative", "neutral", "mixed"]
    critical_events: list[dict[str, Any]] = Field(default_factory=list)
    alignment_with_scores: str = Field(min_length=1)
    confidence_score: float = Field(ge=0, le=1)


class ComposerOutput(BaseModel):
    content: str = Field(min_length=1)
    confidence_score: float = Field(ge=0, le=1)


class QualityReviewOutput(BaseModel):
    issues_found: list[str] = Field(default_factory=list)
    suggested_fixes: list[str] = Field(default_factory=list)
    overall_quality_score: float = Field(ge=0, le=1)
    approved: bool


class PipelineMetadata(BaseModel):
    pipeline: str = "ai-agent-v2"
    agents_used: list[str] = Field(default_factory=list)
    model: str = ""
    tokens_used: dict[str, int] = Field(default_factory=dict)
    generation_time_seconds: float = 0.0
    confidence_score: float = Field(default=0.0, ge=0, le=1)
    fallback_used: bool = False
    fallback_reason: str | None = None
    cache_hits: int = 0
    quality_score: float | None = Field(default=None, ge=0, le=1)


class AIReportResult(BaseModel):
    content: str
    generatedAt: str
    metadata: PipelineMetadata


class ToneValidatorMixin:
    @field_validator("tone", mode="before", check_fields=False)
    @classmethod
    def _tone_int(cls, v):  # type: ignore[no-untyped-def]
        if v is None:
            return 2
        iv = int(v)
        if iv < 0 or iv > 4:
            raise ValueError("tone must be between 0 and 4")
        return iv
