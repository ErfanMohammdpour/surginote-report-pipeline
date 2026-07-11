"""Agent 4 — synthesize Markdown clinical report."""

from __future__ import annotations

from typing import Any

from app.application.ai_pipeline.base_agent import BaseAgent
from app.application.ai_pipeline.schemas import ComposerOutput
from app.domain.errors import AgentValidationError
from app.infrastructure.llm.llm_client import LLMClient

REQUIRED_MARKDOWN_MARKERS: tuple[str, ...] = (
    "# Surgical Procedure Evaluation Report",
    "## Executive Summary",
    "## Overall Assessment",
    "## Recommendations",
)


class ReportComposerAgent(BaseAgent):
    output_model = ComposerOutput

    def __init__(self, llm_client: LLMClient, **kwargs: Any) -> None:
        super().__init__(
            agent_name="report_composer",
            prompt_file="report_composition.txt",
            llm_client=llm_client,
            **kwargs,
        )

    def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "phase_analyses": input_data.get("phase_analyses", []),
            "markers_analysis": input_data.get("markers_analysis", {}),
            "settings": input_data.get("settings", {}),
            "normalized": input_data.get("normalized", {}),
        }
        revision_notes = input_data.get("revision_notes")
        if revision_notes:
            payload["revision_notes"] = revision_notes
        result = self._call_llm_json(payload)
        self._validate_markdown_structure(result.get("content", ""))
        return result

    @staticmethod
    def _validate_markdown_structure(content: str) -> None:
        missing = [marker for marker in REQUIRED_MARKDOWN_MARKERS if marker not in content]
        if missing:
            raise AgentValidationError(
                f"Composer output missing required sections: {', '.join(missing)}",
                agent="report_composer",
                errors=[{"path": "content", "message": f"Missing {m}"} for m in missing],
            )
