"""Idempotent multi-format import with events + object storage."""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.domain.errors import IdempotencyConflict, ParseError, StorageError, UploadError, ValidationError
from app.domain.events import (
    EVENT_IMPORT_FAILED,
    EVENT_IMPORT_STARTED,
    EVENT_NORMALIZATION_COMPLETED,
    EVENT_STORAGE_COMPLETED,
    EVENT_VALIDATION_COMPLETED,
    ImportEvent,
)
from app.domain.hashing import sha256_bytes
from app.domain.validation import validate_canonical
from app.infrastructure.database.events_repo import ImportEventRepository
from app.infrastructure.database.models import IdempotencyORM, ImportORM
from app.infrastructure.database.repository import SqlAlchemyCaseRepository
from app.infrastructure.parsers.multi import parse_upload
from app.infrastructure.storage.s3 import put_object


def _emit(repo: ImportEventRepository, import_id: str, event_type: str, payload: dict) -> None:
    repo.append(ImportEvent(import_id=import_id, event_type=event_type, payload=payload))


def _read_upload_bounded(file_like: io.BytesIO, *, max_bytes: int) -> bytes:
    data = file_like.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise UploadError("file_too_large", f"Max upload size is {max_bytes} bytes")
    if not data:
        raise UploadError("empty_upload", "Upload body is empty — possible interrupted transfer")
    return data


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_idempotent_cached(session: Session, key: str) -> tuple[dict, dict] | None:
    now = _utc_now()
    row = session.get(IdempotencyORM, key)
    if row is None:
        return None
    exp = row.expires_at.replace(tzinfo=None) if row.expires_at and row.expires_at.tzinfo else row.expires_at
    if exp and exp < now:
        session.delete(row)
        session.flush()
        return None
    return row.response_body, row.response_headers or {}


def save_idempotent(session: Session, key: str, body: dict, headers: dict | None = None) -> None:
    ttl = timedelta(hours=settings.idempotency_ttl_hours)
    now = _utc_now()
    session.merge(
        IdempotencyORM(
            key=key,
            response_body=body,
            response_headers=headers or {},
            created_at=now,
            expires_at=now + ttl,
        )
    )


def _fail_import(
    session: Session,
    ev_repo: ImportEventRepository,
    imp: ImportORM,
    *,
    stage: str,
    payload: dict,
    idempotency_key: str | None,
) -> None:
    imp.status = "failed"
    _emit(ev_repo, imp.id, EVENT_IMPORT_FAILED, {"stage": stage, **payload})
    if idempotency_key:
        save_idempotent(
            session,
            idempotency_key,
            {
                "import_id": imp.id,
                "status": "failed",
                "stage": stage,
                **payload,
            },
        )
    session.commit()


def process_import(
    session: Session,
    *,
    filename: str,
    file_like: io.BytesIO,
    content_type: str | None,
    idempotency_key: str | None,
    user_id: str | None = None,
    skip_storage: bool = False,
) -> tuple[dict[str, Any], dict[str, str], bool]:
    """Returns (response_body, response_headers, is_replay)."""
    headers: dict[str, str] = {}

    if idempotency_key:
        cached = get_idempotent_cached(session, idempotency_key)
        if cached:
            body, hdrs = cached
            if body.get("status") == "failed":
                return body, {**hdrs, "X-Idempotent-Replay": "true"}, True
            return body, {**hdrs, "X-Idempotent-Replay": "true"}, True

    payload = _read_upload_bounded(file_like, max_bytes=settings.max_upload_bytes)
    digest = sha256_bytes(payload)

    if idempotency_key:
        prior = session.query(ImportORM).filter(ImportORM.idempotency_key == idempotency_key).order_by(ImportORM.created_at.desc()).first()
        if prior and prior.file_hash_sha256 and prior.file_hash_sha256 != digest:
            raise IdempotencyConflict("idempotency_key_reused_with_different_body")

    imp = ImportORM(
        idempotency_key=idempotency_key,
        filename=filename,
        content_type=content_type,
        file_size_bytes=len(payload),
        file_hash_sha256=digest,
        status="processing",
    )
    session.add(imp)
    session.flush()

    ev_repo = ImportEventRepository(session)
    _emit(
        ev_repo,
        imp.id,
        EVENT_IMPORT_STARTED,
        {"filename": filename, "file_size_bytes": len(payload), "file_hash_sha256": digest},
    )

    try:
        parsed, canonical, fmt = parse_upload(filename=filename, payload=payload, content_type=content_type)
    except ValueError as e:
        _fail_import(
            session,
            ev_repo,
            imp,
            stage="parse",
            payload={"message": str(e), "code": "parse_error"},
            idempotency_key=idempotency_key,
        )
        raise ParseError(str(e)) from e
    except (ParseError, UploadError) as e:
        msg = str(e)
        code = getattr(e, "code", "parse_error")
        _fail_import(
            session,
            ev_repo,
            imp,
            stage="parse",
            payload={"message": msg, "code": code},
            idempotency_key=idempotency_key,
        )
        raise

    imp.format = fmt
    validation = validate_canonical(canonical)
    _emit(ev_repo, imp.id, EVENT_VALIDATION_COMPLETED, validation)
    if not validation["valid"]:
        _fail_import(
            session,
            ev_repo,
            imp,
            stage="validation",
            payload={"errors": validation["errors"]},
            idempotency_key=idempotency_key,
        )
        raise ValidationError(validation["errors"])

    _emit(ev_repo, imp.id, EVENT_NORMALIZATION_COMPLETED, {"format": fmt, "records": len(canonical.get("skills") or [])})

    storage_key = None
    if not skip_storage and not settings.skip_object_storage:
        try:
            storage_key = f"imports/{imp.id}/{filename}"
            put_object(key=storage_key, body=payload, content_type=content_type or "application/octet-stream")
            imp.storage_key = storage_key
            _emit(ev_repo, imp.id, EVENT_STORAGE_COMPLETED, {"storage_key": storage_key, "sha256": digest})
        except StorageError as e:
            _fail_import(
                session,
                ev_repo,
                imp,
                stage="storage",
                payload={"message": str(e)},
                idempotency_key=idempotency_key,
            )
            raise

    repo = SqlAlchemyCaseRepository(session)
    sources = ["xlsx_normalized" if fmt == "xlsx" else f"{fmt}_import"]
    if parsed.raw_payload:
        sources.append("raw_json_enriched")
    case = repo.persist_parsed_bundle(
        video_info=parsed.video_info,
        phases=parsed.phases,
        skills=parsed.skill_rows,
        comments=parsed.comments,
        raw_payload=parsed.raw_payload,
        sources_used=sources,
    )
    imp.case_id = case.id
    imp.canonical_snapshot = canonical
    imp.status = "completed"

    body = {
        "import_id": imp.id,
        "case_id": case.id,
        "status": "completed",
        "warnings": list(parsed.warnings),
        "file_hash_sha256": digest,
        "storage_key": storage_key,
        "format": fmt,
    }
    if idempotency_key:
        save_idempotent(session, idempotency_key, body, headers)
    session.commit()
    return body, headers, False
