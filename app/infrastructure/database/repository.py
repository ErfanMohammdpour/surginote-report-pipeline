from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.errors import DomainError
from app.infrastructure.database import models


@dataclass
class SqlAlchemyCaseRepository:
    session: Session

    def persist_parsed_bundle(
        self,
        *,
        video_info: dict,
        phases: list[dict],
        skills: list[dict],
        comments: list[dict],
        raw_payload: dict | None,
        sources_used: list[str],
    ) -> models.CaseORM:
        case = models.CaseORM(sources_used=sources_used, raw_payload=raw_payload)

        def _gv(key_variants: tuple[str, ...]) -> object | None:
            for k in key_variants:
                if k in video_info:
                    return video_info.get(k)
            return None

        case.video_id = _maybe_int(_gv(("Video ID",)))
        case.video_name = _maybe_str(_gv(("Video Name",)))
        case.procedure_description = _maybe_str(_gv(("Description",)))
        case.duration_seconds = _maybe_float(_gv(("Duration (seconds)",)))
        case.file_size_bytes = _maybe_int(_gv(("File Size (bytes)",)))
        case.upload_date = _maybe_str(_gv(("Upload Date",)))
        case.export_date = _maybe_str(_gv(("Export Date",)))
        case.owner_email = _maybe_str(_gv(("Owner Email",)))
        case.export_version = _maybe_str(_gv(("Export Version",)))
        case.total_annotation_versions = _maybe_int(_gv(("Total Annotation Versions",)))
        case.annotation_author = _maybe_str(_gv(("Created By",)))  # LATEST ANNOTATION subsection row
        case.annotation_created_at = _maybe_str(_gv(("Created At",)))

        case.phases = [
            models.PhaseORM(
                phase_name=p["phase_name"],
                short_name=p.get("short_name"),
                start_time_display=p.get("start_time_display"),
                end_time_display=p.get("end_time_display"),
                duration_display=p.get("duration_display"),
                start_seconds=p.get("start_seconds"),
                end_seconds=p.get("end_seconds"),
                start_frame=p.get("start_frame"),
                end_frame=p.get("end_frame"),
                description=p.get("description"),
                is_custom=p.get("is_custom"),
                phaco_method=p.get("phaco_method"),
            )
            for p in phases
        ]

        case.skills = [
            models.SkillRatingORM(
                phase_name=s["phase_name"],
                skill_name=s["skill_name"],
                score=float(s["score"]),
                max_score=float(s["max_score"]),
            )
            for s in skills
        ]

        markers = []
        if isinstance(raw_payload, dict):
            markers = raw_payload.get("markers") or []
        markers_by_title = {}
        if isinstance(markers, list):
            for m in markers:
                if isinstance(m, dict) and m.get("title"):
                    markers_by_title[str(m["title"])] = m

        cm_rows: list[models.CommentORM] = []
        for c in comments:
            title = c.get("title")
            blob = markers_by_title.get(str(title)) if title else None
            audio_url = None
            marker_id = None
            ctype = str(c.get("comment_type") or "unknown").lower()
            if isinstance(blob, dict):
                marker_id = str(blob.get("id") or "") or None
                audio_url = blob.get("audioUrl")
                if ctype == "unknown" or ctype == "":
                    t = blob.get("type")
                    ctype = str(t).lower() if t else ctype

            cm_rows.append(
                models.CommentORM(
                    sort_index=int(c.get("sort_index") or 0),
                    marker_id=marker_id,
                    video_time_display=c.get("video_time_display"),
                    timestamp_seconds=c.get("timestamp_seconds"),
                    comment_type=ctype,
                    title=c.get("title"),
                    text=c.get("text"),
                    audio_url=audio_url,
                )
            )
        case.comments = cm_rows

        self.session.add(case)
        self.session.flush()
        return case

    def get_case(self, case_id: str) -> models.CaseORM:
        stmt = (
            select(models.CaseORM)
            .where(models.CaseORM.id == case_id)
            .options(
                selectinload(models.CaseORM.phases),
                selectinload(models.CaseORM.skills),
                selectinload(models.CaseORM.comments),
            )
        )
        hit = self.session.execute(stmt).scalar_one_or_none()
        if hit is None:
            raise DomainError("case_not_found")
        return hit

    def add_report(self, case_id: str, payload: dict, schema_version: str) -> models.ReportORM:
        r = models.ReportORM(case_id=case_id, payload=payload, schema_version=schema_version)
        self.session.add(r)
        self.session.flush()
        return r

    def latest_report(self, case_id: str) -> models.ReportORM | None:
        stmt = select(models.ReportORM).where(models.ReportORM.case_id == case_id).order_by(models.ReportORM.id.desc()).limit(1)
        return self.session.execute(stmt).scalar_one_or_none()


def _maybe_int(v):
    try:
        if v is None or v == "":
            return None
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _maybe_float(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _maybe_str(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None
