"""Agent 1 — validate + normalize annotation_data (hybrid deterministic path)."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.application.ai_pipeline.base_agent import BaseAgent
from app.application.ai_pipeline.schemas import AnnotationPayload, NormalizedData
from app.domain.errors import AgentInputError
from app.infrastructure.llm.llm_client import LLMClient


class DataExtractorAgent(BaseAgent):
    output_model = NormalizedData

    def __init__(self, llm_client: LLMClient, **kwargs: Any) -> None:
        super().__init__(
            agent_name="data_extractor",
            prompt_file="data_extractor.txt",
            llm_client=llm_client,
            **kwargs,
        )

    def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        try:
            payload = AnnotationPayload.model_validate(input_data)
        except ValidationError as exc:
            return {"error": f"Invalid annotation_data: {exc.errors()[0]['msg']}", "normalized": None}

        if not payload.phases:
            return {"error": "At least one phase is required", "normalized": None}

        normalized = NormalizedData(
            normalized_phases=sorted(payload.phases, key=lambda p: p.startTime or 0),
            normalized_markers=sorted(payload.markers, key=lambda m: m.timestamp),
            metrics=payload.metrics,
            scores=payload.scores,
            metadata={
                "version": payload.version,
                "savedAt": payload.savedAt,
                "phase_count": len(payload.phases),
                "marker_count": len(payload.markers),
            },
        )

        if self._requires_llm_enrichment(input_data):
            llm_out = self._call_llm_json(normalized.model_dump(mode="json"))
            if llm_out.get("error"):
                return {"error": str(llm_out["error"]), "normalized": None}
            return llm_out

        return normalized.model_dump(mode="json")

    @staticmethod
    def _requires_llm_enrichment(input_data: dict[str, Any]) -> bool:
        return bool(input_data.get("force_llm_normalize"))

    def require_valid_normalized(self, result: dict[str, Any]) -> NormalizedData:
        if result.get("error") or result.get("normalized") is None and "normalized_phases" not in result:
            if result.get("error"):
                raise AgentInputError(str(result["error"]), agent=self.agent_name)
            raise AgentInputError("Data extraction failed", agent=self.agent_name)
        if "normalized_phases" in result:
            return NormalizedData.model_validate(result)
        raise AgentInputError("Data extraction returned no normalized payload", agent=self.agent_name)
