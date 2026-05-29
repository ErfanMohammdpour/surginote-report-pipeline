from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class CaseORM(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    procedure_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    upload_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    export_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    owner_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    export_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    total_annotation_versions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    annotation_author: Mapped[str | None] = mapped_column(String(256), nullable=True)
    annotation_created_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sources_used: Mapped[list[str]] = mapped_column(JSON, default=list)

    raw_payload: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    phases: Mapped[list[PhaseORM]] = relationship(back_populates="case", cascade="all, delete-orphan")
    skills: Mapped[list[SkillRatingORM]] = relationship(back_populates="case", cascade="all, delete-orphan")
    comments: Mapped[list[CommentORM]] = relationship(back_populates="case", cascade="all, delete-orphan")
    reports: Mapped[list[ReportORM]] = relationship(back_populates="case", cascade="all, delete-orphan")


class PhaseORM(Base):
    __tablename__ = "case_phases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True)

    phase_name: Mapped[str] = mapped_column(String(256))
    short_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    start_time_display: Mapped[str | None] = mapped_column(String(32), nullable=True)
    end_time_display: Mapped[str | None] = mapped_column(String(32), nullable=True)
    duration_display: Mapped[str | None] = mapped_column(String(32), nullable=True)
    start_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_frame: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_frame: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_custom: Mapped[bool | None] = mapped_column(nullable=True)
    phaco_method: Mapped[str | None] = mapped_column(String(64), nullable=True)

    case: Mapped[CaseORM] = relationship(back_populates="phases")


class SkillRatingORM(Base):
    __tablename__ = "case_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True)

    phase_name: Mapped[str] = mapped_column(String(256))
    skill_name: Mapped[str] = mapped_column(String(512))
    score: Mapped[float] = mapped_column(Float)
    max_score: Mapped[float] = mapped_column(Float)

    case: Mapped[CaseORM] = relationship(back_populates="skills")


class CommentORM(Base):
    __tablename__ = "case_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True)

    sort_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    marker_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    video_time_display: Mapped[str | None] = mapped_column(String(32), nullable=True)
    timestamp_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    comment_type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    case: Mapped[CaseORM] = relationship(back_populates="comments")


class ReportORM(Base):
    __tablename__ = "case_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True)

    schema_version: Mapped[str] = mapped_column(String(32), default="1.1.0")
    payload: Mapped[dict] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case: Mapped[CaseORM] = relationship(back_populates="reports")


class ImportORM(Base):
    __tablename__ = "imports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: f"imp_{uuid.uuid4().hex[:12]}")
    case_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("cases.id", ondelete="SET NULL"), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_hash_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    format: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    canonical_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    events: Mapped[list[ImportEventORM]] = relationship(back_populates="import_row", cascade="all, delete-orphan")
    async_reports: Mapped[list[AsyncReportORM]] = relationship(back_populates="import_row", cascade="all, delete-orphan")


class ImportEventORM(Base):
    __tablename__ = "import_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    import_id: Mapped[str] = mapped_column(String(36), ForeignKey("imports.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    import_row: Mapped[ImportORM] = relationship(back_populates="events")


class IdempotencyORM(Base):
    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    response_body: Mapped[dict] = mapped_column(JSON)
    response_headers: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AsyncReportORM(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: f"rpt_{uuid.uuid4().hex[:12]}")
    import_id: Mapped[str] = mapped_column(String(36), ForeignKey("imports.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("cases.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="processing")
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    schema_version: Mapped[str] = mapped_column(String(16), default="2.0")
    locale: Mapped[str] = mapped_column(String(8), default="en")
    final_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    config_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    import_row: Mapped[ImportORM] = relationship(back_populates="async_reports")
    sections: Mapped[list[ReportSectionORM]] = relationship(back_populates="report", cascade="all, delete-orphan")


class ReportSectionORM(Base):
    __tablename__ = "report_sections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id: Mapped[str] = mapped_column(String(36), ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    section_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    report: Mapped[AsyncReportORM] = relationship(back_populates="sections")


class WebhookORM(Base):
    __tablename__ = "webhooks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    url: Mapped[str] = mapped_column(String(2048))
    events: Mapped[list[str]] = mapped_column(JSON, default=list)
    secret: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
