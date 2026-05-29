from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class Provenance(BaseModel):
    source_records: list[str] = Field(default_factory=list)
    calculation_method: str
    input_values: list[Any] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    analyzer_version: str
    config_snapshot: dict[str, Any] | None = None


class AnalysisResult(BaseModel):
    analyzer_name: str
    analyzer_version: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance


class BaseAnalyzer(ABC):
    @abstractmethod
    def analyze(self, normalized_data: dict[str, Any]) -> AnalysisResult:
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass
