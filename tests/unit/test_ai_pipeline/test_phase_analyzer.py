from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from app.application.ai_pipeline.agents.phase_analyzer import PhaseAnalyzerAgent
from app.infrastructure.llm.types import ChatResult, LLMProvider

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "mock_llm_responses"


def _chat_from_file(name: str) -> ChatResult:
    text = (_FIXTURES / name).read_text(encoding="utf-8")
    return ChatResult(text=text, provider=LLMProvider.GEMINI, model="test", tokens_in=5, tokens_out=8)


def test_phase_analyzer_returns_schema_fields():
    mock_llm = MagicMock()
    mock_llm.chat.return_value = _chat_from_file("phase_analysis_rhexis.json")
    agent = PhaseAnalyzerAgent(mock_llm, max_retries=1)
    out = agent.process(
        {
            "phase": {"id": "phase_rhexis", "name": "Rhexis"},
            "metrics": [{"id": "r1", "name": "Microscope use"}],
            "scores": {"r1": 5.0},
            "tone": 2,
        }
    )
    assert out["phase_id"] == "phase_rhexis"
    assert out["clinical_narrative"]
    assert out["confidence_score"] == 0.92


def test_phase_analyzer_failure_template():
    tpl = PhaseAnalyzerAgent.failure_template("phase_x")
    assert tpl["phase_id"] == "phase_x"
    assert tpl["confidence_score"] == 0.0
