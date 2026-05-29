"""Multi-stage async report generation with provenance."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.application.analyzers import ContradictionAnalyzer, ScoreAnalyzer, TimelineAnalyzer
from app.application.report_notifications import finalize_report
from app.application.rules.engine import load_rules_config
from app.infrastructure.database.models import AsyncReportORM, ImportORM, ReportSectionORM

STAGES = (
    ("phase_summary", "PhaseAnalyzer_v1.2"),
    ("score_analysis", "ScoreAnalyzer_v2.0"),
    ("comment_timeline", "TimelineAnalyzer_v1.0"),
    ("contradictions", "ContradictionAnalyzer_v1.5"),
)

MAX_STAGE_ATTEMPTS = 3


def _section(session: Session, report_id: str, name: str) -> ReportSectionORM:
    return (
        session.query(ReportSectionORM)
        .filter(ReportSectionORM.report_id == report_id, ReportSectionORM.section_name == name)
        .one()
    )


def _mark_processing(sec: ReportSectionORM) -> None:
    sec.status = "processing"
    sec.started_at = datetime.now(timezone.utc)
    sec.error_message = None


def _mark_done(sec: ReportSectionORM, data: dict) -> None:
    sec.status = "completed"
    sec.data = data
    sec.completed_at = datetime.now(timezone.utc)


def _mark_failed(sec: ReportSectionORM, msg: str, retry_count: int) -> None:
    sec.status = "failed"
    sec.error_message = msg
    sec.retry_count = retry_count
    sec.completed_at = datetime.now(timezone.utc)


def create_async_report(
    session: Session,
    *,
    import_id: str,
    case_id: str | None,
    locale: str,
    config_snapshot: dict | None = None,
    supersedes_report_id: str | None = None,
) -> AsyncReportORM:
    snap = dict(config_snapshot or {})
    if supersedes_report_id:
        snap["supersedes_report_id"] = supersedes_report_id
    report = AsyncReportORM(
        import_id=import_id,
        case_id=case_id,
        locale=locale,
        status="processing",
        config_snapshot=snap,
    )
    session.add(report)
    session.flush()
    for name, _ in STAGES:
        session.add(ReportSectionORM(report_id=report.id, section_name=name, status="pending"))
    session.flush()
    return report


def run_stage(session: Session, report_id: str, stage_name: str) -> dict[str, Any]:
    report = session.get(AsyncReportORM, report_id)
    if report is None:
        raise ValueError("report_not_found")

    imp = session.get(ImportORM, report.import_id)
    canonical = (imp.canonical_snapshot if imp else None) or {}
    sec = _section(session, report_id, stage_name)
    _mark_processing(sec)
    session.flush()

    try:
        if stage_name == "phase_summary":
            data = {
                "version": "1.0",
                "generated_by": "PhaseAnalyzer_v1.2",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "total_phases": len(canonical.get("phases") or []),
                    "phases": canonical.get("phases") or [],
                },
            }
        elif stage_name == "score_analysis":
            res = ScoreAnalyzer().analyze(canonical)
            data = {
                "version": "1.1",
                "generated_by": f"{res.analyzer_name}_v{res.analyzer_version}",
                "generated_at": res.timestamp.isoformat(),
                "data": res.data,
                "provenance": res.provenance.model_dump(mode="json"),
            }
        elif stage_name == "comment_timeline":
            res = TimelineAnalyzer().analyze(canonical)
            data = {
                "version": "1.0",
                "generated_by": f"{res.analyzer_name}_v{res.analyzer_version}",
                "generated_at": res.timestamp.isoformat(),
                "data": res.data,
                "provenance": res.provenance.model_dump(mode="json"),
            }
        elif stage_name == "contradictions":
            cfg = report.config_snapshot or load_rules_config()
            res = ContradictionAnalyzer(rules_config=cfg, locale=report.locale).analyze(canonical)
            data = {
                "version": "1.0",
                "generated_by": f"{res.analyzer_name}_v{res.analyzer_version}",
                "generated_at": res.timestamp.isoformat(),
                "data": res.data,
                "provenance": res.provenance.model_dump(mode="json"),
            }
        else:
            raise ValueError(f"unknown_stage:{stage_name}")

        _mark_done(sec, data)
        _update_progress(session, report)
        session.commit()
        return {"status": "success", "section": stage_name}

    except Exception as e:  # noqa: BLE001
        sec.retry_count = (sec.retry_count or 0) + 1
        if sec.retry_count >= MAX_STAGE_ATTEMPTS:
            _mark_failed(sec, str(e), sec.retry_count)
            report.status = "failed"
            session.commit()
            return {"status": "failed", "section": stage_name, "error": str(e)}
        sec.status = "pending"
        sec.error_message = str(e)
        session.commit()
        return {"status": "retry", "section": stage_name, "attempt": sec.retry_count, "error": str(e)}


def _update_progress(session: Session, report: AsyncReportORM) -> None:
    session.refresh(report)
    sections = list(report.sections)
    done = sum(1 for s in sections if s.status == "completed")
    report.progress_percent = int(100 * done / max(len(sections), 1))
    if done == len(sections):
        report.status = "completed"
        report.completed_at = datetime.now(timezone.utc)
        report.final_payload = assemble_final_report(report)


def assemble_final_report(report: AsyncReportORM) -> dict:
    sections_out = {}
    for sec in report.sections:
        if sec.data:
            sections_out[sec.section_name] = sec.data

    # processing_time_ms — from report created_at to completed_at
    processing_time_ms = None
    if report.completed_at and report.created_at:
        ca = report.created_at.replace(tzinfo=None) if report.created_at.tzinfo else report.created_at
        co = report.completed_at.replace(tzinfo=None) if report.completed_at.tzinfo else report.completed_at
        processing_time_ms = max(0, int((co - ca).total_seconds() * 1000))

    meta: dict = {
        "processing_time_ms": processing_time_ms,
        "stages_executed": len(report.sections),
        "stages_failed": sum(1 for s in report.sections if s.status == "failed"),
        "total_events_processed": _count_events(report),
    }
    if report.config_snapshot and report.config_snapshot.get("supersedes_report_id"):
        meta["supersedes_report_id"] = report.config_snapshot["supersedes_report_id"]
    return {
        "report_id": report.id,
        "schema_version": report.schema_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_import_id": report.import_id,
        "locale": report.locale,
        "sections": sections_out,
        "metadata": meta,
    }


def _count_events(report: AsyncReportORM) -> int:
    """Best-effort total event count across all section data."""
    total = 0
    for sec in report.sections:
        if not sec.data:
            continue
        data = sec.data.get("data") or {}
        # phases, comments, flags, etc.
        for key in ("phases", "comments", "flags"):
            val = data.get(key)
            if isinstance(val, list):
                total += len(val)
        if "skills" in data:
            total += len(data.get("skills") or [])
    return total or len(report.sections)


def run_all_stages_sync(session: Session, report_id: str) -> AsyncReportORM | None:
    for name, _ in STAGES:
        for _attempt in range(MAX_STAGE_ATTEMPTS):
            result = run_stage(session, report_id, name)
            if result["status"] == "success":
                break
            if result["status"] == "failed":
                finalize_report(session, report_id)
                return session.get(AsyncReportORM, report_id)
        else:
            finalize_report(session, report_id)
            return session.get(AsyncReportORM, report_id)
    finalize_report(session, report_id)
    return session.get(AsyncReportORM, report_id)
