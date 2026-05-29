from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.locale_util import resolve_report_locale
from app.application.report_diff import diff_reports
from app.application.report_jobs import create_async_report, run_all_stages_sync
from app.application.report_notifications import finalize_report
from app.application.rules.engine import load_rules_config
from app.config import settings
from app.domain.security import sanitize_filename, validate_webhook_url
from app.infrastructure.database.events_repo import ImportEventRepository
from app.infrastructure.database.models import AsyncReportORM, ImportORM, ReportSectionORM, WebhookORM
from app.infrastructure.queue.enqueue import enqueue_report_pipeline


class RegenerateBody(BaseModel):
    override_rules: list[dict] | None = None
    override_thresholds: dict[str, Any] | None = None
    locale: str | None = None


class WebhookCreate(BaseModel):
    url: str
    events: list[str] = Field(default_factory=lambda: ["report.completed", "report.failed"])
    secret: str = Field(min_length=16, max_length=256)

    @field_validator("url")
    @classmethod
    def url_must_be_valid(cls, v: str) -> str:
        validate_webhook_url(v)
        return v

    @field_validator("events")
    @classmethod
    def events_must_be_known(cls, v: list[str]) -> list[str]:
        allowed = {"report.completed", "report.failed", "import.completed"}
        for ev in v:
            if ev not in allowed:
                raise ValueError(f"unknown event type: {ev!r}. allowed: {sorted(allowed)}")
        return v


def _section_to_dict(sec: ReportSectionORM, *, include_duration: bool = True) -> dict:
    item: dict = {"name": sec.section_name, "status": sec.status}
    if sec.completed_at:
        item["completed_at"] = sec.completed_at.isoformat()
    if include_duration and sec.started_at and sec.completed_at:
        sa = sec.started_at.replace(tzinfo=None) if sec.started_at.tzinfo else sec.started_at
        ca = sec.completed_at.replace(tzinfo=None) if sec.completed_at.tzinfo else sec.completed_at
        item["duration_ms"] = max(0, int((ca - sa).total_seconds() * 1000))
    if sec.error_message:
        item["error_message"] = sec.error_message
    return item


def _estimate_completion(report: AsyncReportORM) -> str | None:
    """Rough ETA based on average stage duration so far."""
    completed = [s for s in report.sections if s.status == "completed" and s.started_at and s.completed_at]
    if not completed:
        return None
    durations = []
    for s in completed:
        sa = s.started_at.replace(tzinfo=None) if s.started_at.tzinfo else s.started_at
        ca = s.completed_at.replace(tzinfo=None) if s.completed_at.tzinfo else s.completed_at
        durations.append((ca - sa).total_seconds())
    avg_secs = sum(durations) / len(durations)
    pending_count = sum(1 for s in report.sections if s.status in ("pending", "processing"))
    if pending_count == 0:
        return None
    from datetime import timedelta
    est = datetime.now(timezone.utc) + timedelta(seconds=avg_secs * pending_count)
    return est.isoformat()


def get_pipeline_router() -> APIRouter:
    r = APIRouter(prefix="/v1")

    # ── async report ──────────────────────────────────────────────────────────
    @r.post("/imports/{import_id}/reports/async")
    async def start_async_report(
        request: Request,
        import_id: str,
        locale: str | None = Query(None),
        session: Session = Depends(get_db),
    ):
        import_id = sanitize_filename(import_id)
        row = session.get(ImportORM, import_id)
        if row is None:
            raise HTTPException(404, detail={"code": "import_not_found"})
        if row.status != "completed":
            raise HTTPException(409, detail={"code": "import_not_completed", "status": row.status})
        if not row.canonical_snapshot:
            raise HTTPException(422, detail={"code": "missing_canonical_snapshot"})

        rl = resolve_report_locale(locale, settings.report_locale)
        cfg = load_rules_config()
        report = create_async_report(session, import_id=import_id, case_id=row.case_id, locale=rl, config_snapshot=cfg)
        session.commit()

        if settings.sync_jobs:
            run_all_stages_sync(session, report.id)
        else:
            await enqueue_report_pipeline(request.app.state, report.id)

        session.refresh(report)
        return {
            "report_id": report.id,
            "status": report.status,
            "progress_percent": report.progress_percent,
            "async": not settings.sync_jobs,
        }

    # ── report status ─────────────────────────────────────────────────────────
    @r.get("/reports/{report_id}/status")
    def report_status(report_id: str, session: Session = Depends(get_db)):
        report = session.get(AsyncReportORM, report_id)
        if report is None:
            raise HTTPException(404, detail={"code": "report_not_found"})

        completed = [_section_to_dict(s) for s in report.sections if s.status == "completed"]
        pending_names = [s.section_name for s in report.sections if s.status not in ("completed",)]

        resp: dict = {
            "report_id": report.id,
            "status": report.status,
            "progress_percent": report.progress_percent,
            "completed_stages": completed,
            "pending_stages": pending_names,
        }
        if report.status not in ("completed", "failed"):
            est = _estimate_completion(report)
            if est:
                resp["estimated_completion"] = est
        if report.status == "completed" and report.created_at and report.completed_at:
            ca = report.created_at.replace(tzinfo=None)
            co = report.completed_at.replace(tzinfo=None)
            resp["duration_ms"] = max(0, int((co - ca).total_seconds() * 1000))
        return resp

    # ── get report payload ────────────────────────────────────────────────────
    @r.get("/reports/{report_id}")
    def get_report(report_id: str, session: Session = Depends(get_db)):
        report = session.get(AsyncReportORM, report_id)
        if report is None or not report.final_payload:
            raise HTTPException(404, detail={"code": "report_not_ready"})
        return report.final_payload

    # ── diff ──────────────────────────────────────────────────────────────────
    @r.get("/reports/{id1}/diff/{id2}")
    def reports_diff(id1: str, id2: str, session: Session = Depends(get_db)):
        a = session.get(AsyncReportORM, id1)
        b = session.get(AsyncReportORM, id2)
        if not a or not b or not a.final_payload or not b.final_payload:
            raise HTTPException(404, detail={"code": "report_not_ready"})
        return diff_reports(a.final_payload, b.final_payload)

    # ── regenerate ────────────────────────────────────────────────────────────
    @r.post("/reports/{report_id}/regenerate")
    async def regenerate(
        request: Request,
        report_id: str,
        body: RegenerateBody,
        session: Session = Depends(get_db),
    ):
        old = session.get(AsyncReportORM, report_id)
        if old is None:
            raise HTTPException(404, detail={"code": "report_not_found"})
        cfg = load_rules_config(overrides=body.override_rules)
        if body.override_thresholds:
            cfg["override_thresholds"] = body.override_thresholds
        rl = resolve_report_locale(body.locale or old.locale, settings.report_locale)
        report = create_async_report(
            session,
            import_id=old.import_id,
            case_id=old.case_id,
            locale=rl,
            config_snapshot=cfg,
            supersedes_report_id=old.id,
        )
        session.commit()

        if settings.sync_jobs:
            run_all_stages_sync(session, report.id)
        else:
            await enqueue_report_pipeline(request.app.state, report.id)

        session.refresh(report)
        return {"report_id": report.id, "status": report.status, "supersedes": old.id}

    # ── webhooks ──────────────────────────────────────────────────────────────
    @r.post("/webhooks", status_code=201)
    def register_webhook(body: WebhookCreate, session: Session = Depends(get_db)):
        wh = WebhookORM(url=body.url, events=body.events, secret=body.secret)
        session.add(wh)
        session.commit()
        return {"id": wh.id, "url": wh.url, "events": wh.events}

    # ── audit-trail ───────────────────────────────────────────────────────────
    @r.get("/imports/{import_id}/audit-trail")
    def audit_trail(
        import_id: str,
        event_type: str | None = None,
        from_ts: datetime | None = Query(None, alias="from"),
        to_ts: datetime | None = Query(None, alias="to"),
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
        fmt: str = Query("json", alias="format", pattern="^(json|csv)$"),
        session: Session = Depends(get_db),
    ):
        if session.get(ImportORM, import_id) is None:
            raise HTTPException(404, detail={"code": "import_not_found"})

        repo = ImportEventRepository(session)
        rows = repo.list_for_import(
            import_id, event_type=event_type, from_ts=from_ts, to_ts=to_ts, limit=limit, offset=offset
        )
        total = repo.count_for_import(import_id, event_type=event_type, from_ts=from_ts, to_ts=to_ts)

        events = [
            {
                "event_id": e.event_id,
                "event_type": e.event_type,
                "timestamp": e.timestamp.isoformat(),
                "payload": e.payload,
            }
            for e in rows
        ]

        if fmt == "csv":
            buf = io.StringIO()
            writer = csv.DictWriter(
                buf,
                fieldnames=["event_id", "event_type", "timestamp", "payload"],
                extrasaction="ignore",
            )
            writer.writeheader()
            for ev in events:
                writer.writerow({
                    "event_id": ev["event_id"],
                    "event_type": ev["event_type"],
                    "timestamp": ev["timestamp"],
                    "payload": json.dumps(ev["payload"], ensure_ascii=False),
                })
            return Response(
                content=buf.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="audit-{import_id}.csv"'},
            )

        return {
            "import_id": import_id,
            "total_events": total,
            "offset": offset,
            "limit": limit,
            "events": events,
        }

    return r
