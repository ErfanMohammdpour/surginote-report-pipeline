"""Agent 3 — marker and comment semantic analysis."""

from __future__ import annotations

from typing import Any

from app.application.ai_pipeline.base_agent import BaseAgent
from app.application.ai_pipeline.schemas import MarkersAnalysisOutput
from app.infrastructure.llm.llm_client import LLMClient


class MarkersAnalyzerAgent(BaseAgent):
    output_model = MarkersAnalysisOutput

    def __init__(self, llm_client: LLMClient, **kwargs: Any) -> None:
        super().__init__(
            agent_name="markers_analyzer",
            prompt_file="markers_analysis.txt",
            llm_client=llm_client,
            **kwargs,
        )

    def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        markers = input_data.get("markers") or []
        if not markers:
            return MarkersAnalysisOutput(
                commentary_insights=["No markers or comments were recorded for this case."],
                emotion_trend="neutral",
                critical_events=[],
                alignment_with_scores="No commentary available to compare against scores.",
                confidence_score=1.0,
            ).model_dump()

        payload = {
            "markers": markers,
            "scores": input_data.get("scores", {}),
            "phases": input_data.get("phases", []),
            "tone": input_data.get("tone", 2),
        }
        return self._call_llm_json(payload)
