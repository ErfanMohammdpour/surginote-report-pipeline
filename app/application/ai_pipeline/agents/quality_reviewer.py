"""Agent 5 — quality review before delivery."""

from __future__ import annotations

from typing import Any

from app.application.ai_pipeline.base_agent import BaseAgent
from app.application.ai_pipeline.schemas import QualityReviewOutput
from app.infrastructure.llm.llm_client import LLMClient


class QualityReviewerAgent(BaseAgent):
    output_model = QualityReviewOutput

    def __init__(self, llm_client: LLMClient, **kwargs: Any) -> None:
        super().__init__(
            agent_name="quality_reviewer",
            prompt_file="quality_review.txt",
            llm_client=llm_client,
            **kwargs,
        )

    def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "report": input_data.get("report") or input_data.get("content", ""),
            "settings": input_data.get("settings", {}),
        }
        return self._call_llm_json(payload)
