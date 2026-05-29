from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.events import ImportEvent
from app.infrastructure.database.models import ImportEventORM


class ImportEventRepository:
    def __init__(self, session: Session):
        self.session = session

    def append(self, event: ImportEvent) -> ImportEventORM:
        row = ImportEventORM(
            event_id=event.event_id,
            import_id=event.import_id,
            event_type=event.event_type,
            timestamp=event.timestamp,
            payload=event.payload,
            user_id=event.user_id,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def list_for_import(
        self,
        import_id: str,
        *,
        event_type: str | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ImportEventORM]:
        stmt = select(ImportEventORM).where(ImportEventORM.import_id == import_id)
        if event_type:
            stmt = stmt.where(ImportEventORM.event_type == event_type)
        if from_ts:
            stmt = stmt.where(ImportEventORM.timestamp >= from_ts)
        if to_ts:
            stmt = stmt.where(ImportEventORM.timestamp <= to_ts)
        stmt = stmt.order_by(ImportEventORM.timestamp.asc()).offset(offset).limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def count_for_import(
        self,
        import_id: str,
        *,
        event_type: str | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(ImportEventORM).where(ImportEventORM.import_id == import_id)
        if event_type:
            stmt = stmt.where(ImportEventORM.event_type == event_type)
        if from_ts:
            stmt = stmt.where(ImportEventORM.timestamp >= from_ts)
        if to_ts:
            stmt = stmt.where(ImportEventORM.timestamp <= to_ts)
        return int(self.session.execute(stmt).scalar_one())
