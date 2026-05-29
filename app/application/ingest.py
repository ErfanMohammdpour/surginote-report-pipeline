"""Use cases: ingestion + persistence transaction boundary."""

from __future__ import annotations

from typing import BinaryIO

from sqlalchemy.orm import Session

from app.infrastructure.database.repository import SqlAlchemyCaseRepository
from app.infrastructure.excel.parser import ParsedExport, parse_surginote_xlsx


def ingest_excel_upload(db: Session, file_like: BinaryIO) -> tuple[str, ParsedExport]:
    payload = file_like.read()
    parsed = parse_surginote_xlsx(payload)
    sources = ["xlsx_normalized"]
    if parsed.raw_payload:
        sources.append("raw_json_enriched")

    repo = SqlAlchemyCaseRepository(db)
    case = repo.persist_parsed_bundle(
        video_info=parsed.video_info,
        phases=parsed.phases,
        skills=parsed.skill_rows,
        comments=parsed.comments,
        raw_payload=parsed.raw_payload,
        sources_used=sources,
    )
    db.commit()
    db.refresh(case)
    return case.id, parsed
