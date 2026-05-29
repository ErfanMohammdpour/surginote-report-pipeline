from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ImportEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    import_id: str
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)
    user_id: str | None = None


EVENT_IMPORT_STARTED = "ImportStarted"
EVENT_VALIDATION_COMPLETED = "ValidationCompleted"
EVENT_NORMALIZATION_COMPLETED = "NormalizationCompleted"
EVENT_STORAGE_COMPLETED = "StorageCompleted"
EVENT_IMPORT_FAILED = "ImportFailed"
