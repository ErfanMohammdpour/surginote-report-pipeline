"""Agent 2 — per-phase clinical narrative analysis."""

from __future__ import annotations

from typing import Any

from app.application.ai_pipeline.base_agent import BaseAgent
from app.application.ai_pipeline.schemas import PhaseAnalysisOutput
from app.domain.errors import AgentInputError
from app.infrastructure.llm.llm_client import LLMClient


class PhaseAnalyzerAgent(BaseAgent):
    output_model = PhaseAnalysisOutput

    def __init__(self, llm_client: LLMClient, **kwargs: Any) -> None:
        super().__init__(
            agent_name="phase_analyzer",
            prompt_file="phase_analysis.txt",
            llm_client=llm_client,
            **kwargs,
        )

    def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        phase = input_data.get("phase") or {}
        phase_id = str(phase.get("id") or input_data.get("phase_id") or "")
        if not phase_id:
            raise AgentInputError("phase_id is required for phase analysis", agent=self.agent_name)

        payload = {
            "phase": phase,
            "metrics": input_data.get("metrics", []),
            "scores": input_data.get("scores", {}),
            "tone": input_data.get("tone", 2),
            "locale": input_data.get("locale", "en"),
        }
        result = self._call_llm_json(payload)
        if result.get("phase_id") != phase_id:
            result["phase_id"] = phase_id
        return result

    @staticmethod
    def failure_template(phase_id: str) -> dict[str, Any]:
        return PhaseAnalysisOutput(
            phase_id=phase_id,
            clinical_narrative=(
                "Automated narrative unavailable for this phase. "
                "Refer to the skill score table for performance details."
            ),
            strengths=[],
            weaknesses=[],
            recommendations=[],
            key_insights=[],
            confidence_score=0.0,
        ).model_dump()
