from __future__ import annotations

import io
from typing import Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.locale_util import resolve_report_locale
from app.api.schemas import (
    CaseDetailResponse,
    CaseNarrativeRequest,
    CommentDTO,
    ImportResponse,
    NarrativeRequest,
    NarrativeResponse,
    PhaseDTO,
    ReportEnvelope,
    SkillDTO,
)
from app.application.ingest import ingest_excel_upload
from app.application.narrative import synthesize_markdown_report
from app.application.report_pipeline import REPORT_SCHEMA_VERSION, build_json_report
from app.config import settings
from app.domain.errors import DomainError, ParseError
from app.infrastructure.database.models import CaseORM
from app.infrastructure.llm.gemini_rest import GeminiError
from app.infrastructure.database.repository import SqlAlchemyCaseRepository
from app.infrastructure.database.session import get_session


def get_router() -> APIRouter:
    r = APIRouter(prefix="/v1")

    def db():
        yield from get_session()

    def case_to_detail(c: CaseORM) -> CaseDetailResponse:
        return CaseDetailResponse(
            id=c.id,
            video_name=c.video_name,
            video_id=c.video_id,
            export_version=c.export_version,
            duration_seconds=c.duration_seconds,
            has_raw_payload=bool(c.raw_payload),
            created_at=c.created_at,
            phases=[
                PhaseDTO(
                    phase_name=p.phase_name,
                    short_name=p.short_name,
                    start_time_display=p.start_time_display,
                    end_time_display=p.end_time_display,
                    duration_display=p.duration_display,
                    start_seconds=p.start_seconds,
                    end_seconds=p.end_seconds,
                    start_frame=p.start_frame,
                    end_frame=p.end_frame,
                    description=p.description,
                    phaco_method=p.phaco_method,
                )
                for p in c.phases
            ],
            skills=[
                SkillDTO(phase_name=s.phase_name, skill_name=s.skill_name, score=float(s.score), max_score=float(s.max_score))
                for s in c.skills
            ],
            comments=[
                CommentDTO(
                    sort_index=cm.sort_index,
                    video_time_display=cm.video_time_display,
                    timestamp_seconds=float(cm.timestamp_seconds) if cm.timestamp_seconds is not None else None,
                    comment_type=cm.comment_type,
                    title=cm.title,
                    text=cm.text,
                    marker_id=cm.marker_id,
                    audio_url=cm.audio_url,
                )
                for cm in c.comments
            ],
        )

    @r.post("/imports", response_model=ImportResponse)
    async def imports_post(
        upload: UploadFile = File(...),
        locale: str | None = Query(
            None,
            description="Preferred report locale (`en`|`fa`) for follow-up calls; not stored on the case.",
        ),
        session: Session = Depends(db),
    ):
        if not upload.filename or not upload.filename.lower().endswith((".xlsx", ".xlsm")):
            raise HTTPException(status_code=400, detail={"code": "invalid_extension", "message": "only xlsx/xlsm"})
        try:
            content = await upload.read()
            case_id, parsed = ingest_excel_upload(session, io.BytesIO(content))
        except ParseError as e:
            raise HTTPException(status_code=422, detail={"code": "parse_error", "message": str(e)}) from e

        rl = resolve_report_locale(locale, settings.report_locale)
        return ImportResponse(case_id=case_id, warnings=parsed.warnings, default_report_locale=rl)

    @r.get("/cases/{case_id}", response_model=CaseDetailResponse)
    def cases_get(case_id: str, session: Session = Depends(db)):
        repo = SqlAlchemyCaseRepository(session)
        try:
            c = repo.get_case(case_id)
        except DomainError:
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        session.refresh(c)
        return case_to_detail(c)

    @r.post("/cases/{case_id}/reports/generate", response_model=ReportEnvelope)
    def reports_generate(
        case_id: str,
        locale: str | None = Query(
            None,
            description="Structured report template language (`en`|`fa`); default `SN_REPORT_LOCALE`.",
        ),
        persist: bool = True,
        session: Session = Depends(db),
    ):
        repo = SqlAlchemyCaseRepository(session)
        try:
            c = repo.get_case(case_id)
        except DomainError:
            raise HTTPException(status_code=404, detail={"code": "not_found"})

        rl = resolve_report_locale(locale, settings.report_locale)
        body = build_json_report(c, locale=rl)
        rid = None
        if persist:
            row = repo.add_report(case_id, body, REPORT_SCHEMA_VERSION)
            session.commit()
            rid = row.id

        return ReportEnvelope(report=body, persisted_report_id=rid)

    @r.get("/cases/{case_id}/reports/latest", response_model=ReportEnvelope)
    def reports_latest(case_id: str, session: Session = Depends(db)):
        repo = SqlAlchemyCaseRepository(session)
        try:
            repo.get_case(case_id)
        except DomainError:
            raise HTTPException(status_code=404, detail={"code": "not_found"})
        lr = repo.latest_report(case_id)
        if lr is None:
            raise HTTPException(status_code=404, detail={"code": "no_report"})
        return ReportEnvelope(report=lr.payload, persisted_report_id=lr.id)

    def _narrative_from_report_payload(payload: dict, body: NarrativeRequest | CaseNarrativeRequest) -> NarrativeResponse:
        incl = getattr(body, "include_provider_raw", False)
        try:
            res = synthesize_markdown_report(
                report=payload,
                locale=body.locale,
                extra_instructions=body.extra_instructions,
            )
        except ValueError as e:
            if str(e) == "gemini_api_key_missing":
                raise HTTPException(
                    status_code=400,
                    detail={"code": "gemini_api_key_missing", "message": "Set GEMINI_API_KEY in .env"},
                ) from e
            raise HTTPException(status_code=400, detail={"code": "narrative_bad_request", "message": str(e)}) from e
        except GeminiError as e:
            raise HTTPException(
                status_code=502,
                detail={"code": "gemini_upstream_error", "http_status": e.status_code, "body": e.body[:2000]},
            ) from e

        raw = res.get("provider_raw") if incl else None
        return NarrativeResponse(
            markdown=res["markdown"],
            model=res["model"],
            locale=res["locale"],
            finish_reason=res.get("finish_reason"),
            provider_raw=raw,
        )

    @r.post("/narratives/generate", response_model=NarrativeResponse)
    def narratives_generate(body: NarrativeRequest):
        """Send a full structured report JSON body to Gemini for Markdown narrative."""
        return _narrative_from_report_payload(body.report, body)

    @r.post("/narratives/generate-from-report", response_model=NarrativeResponse)
    def narratives_generate_from_report(
        locale: str | None = Query(
            None,
            description="Markdown output language (`en`|`fa`); default `SN_REPORT_LOCALE`.",
        ),
        include_provider_raw: bool = Query(False),
        extra_instructions: str | None = Query(None),
        report: dict[str, Any] = Body(...),
    ):
        """Same narrative as POST /v1/narratives/generate, but the JSON body is only the report object (e.g. file from GET …/reports/latest). Use query string for options; avoids fragile PowerShell ConvertTo-Json wrapping."""
        rl = resolve_report_locale(locale, settings.report_locale)
        body = NarrativeRequest(
            report=report,
            locale=rl,
            extra_instructions=extra_instructions,
            include_provider_raw=include_provider_raw,
        )
        return _narrative_from_report_payload(report, body)

    @r.post("/cases/{case_id}/narratives/generate", response_model=NarrativeResponse)
    def case_narratives_generate(case_id: str, body: CaseNarrativeRequest, session: Session = Depends(db)):
        repo = SqlAlchemyCaseRepository(session)
        try:
            c = repo.get_case(case_id)
        except DomainError:
            raise HTTPException(status_code=404, detail={"code": "not_found"})

        payload: dict
        if body.prefer_persisted_report:
            lr = repo.latest_report(case_id)
            if lr is not None:
                payload = lr.payload
            else:
                payload = build_json_report(c, locale=body.locale)
        else:
            payload = build_json_report(c, locale=body.locale)

        pseudo = NarrativeRequest(
            report=payload,
            locale=body.locale,
            extra_instructions=body.extra_instructions,
            include_provider_raw=body.include_provider_raw,
        )
        return _narrative_from_report_payload(payload, pseudo)

    return r
