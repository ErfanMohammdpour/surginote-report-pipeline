from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ImportResponse(BaseModel):
    case_id: str = Field(description="Stable case id for follow-up API calls")
    warnings: list[str] = Field(default_factory=list)


class PhaseDTO(BaseModel):
    phase_name: str
    short_name: str | None = None
    start_time_display: str | None = None
    end_time_display: str | None = None
    duration_display: str | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None
    start_frame: int | None = None
    end_frame: int | None = None
    description: str | None = None
    phaco_method: str | None = None


class SkillDTO(BaseModel):
    phase_name: str
    skill_name: str
    score: float
    max_score: float


class CommentDTO(BaseModel):
    sort_index: int | None = None
    video_time_display: str | None = None
    timestamp_seconds: float | None = None
    comment_type: str
    title: str | None = None
    text: str | None = None
    marker_id: str | None = None
    audio_url: str | None = None


class CaseDetailResponse(BaseModel):
    id: str
    video_name: str | None = None
    video_id: int | None = None
    export_version: str | None = None
    duration_seconds: float | None = None
    has_raw_payload: bool
    created_at: datetime
    phases: list[PhaseDTO]
    skills: list[SkillDTO]
    comments: list[CommentDTO]


class ReportEnvelope(BaseModel):
    report: dict[str, Any]
    persisted_report_id: int | None = None


class NarrativeRequest(BaseModel):
    """Same structured report JSON shape as POST /v1/cases/{id}/reports/generate returns."""

    report: dict[str, Any]
    locale: str = Field(default="en", description="Locale tag for wording hints (default English)")
    extra_instructions: str | None = Field(default=None, description="Optional extra instructions for the model")
    include_provider_raw: bool = Field(
        default=False,
        description="If true, include full Gemini raw response (large; debugging only)",
    )


class CaseNarrativeRequest(BaseModel):
    locale: str = "en"
    extra_instructions: str | None = None
    prefer_persisted_report: bool = Field(
        default=True,
        description="Use latest persisted report when present; otherwise build fresh from DB",
    )
    include_provider_raw: bool = False


class NarrativeResponse(BaseModel):
    markdown: str
    model: str
    locale: str
    finish_reason: str | None = None
    provider_raw: dict[str, Any] | None = None
