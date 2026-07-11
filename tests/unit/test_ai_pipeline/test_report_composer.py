from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.application.ai_pipeline.agents.report_composer import ReportComposerAgent
from app.domain.errors import AgentValidationError
from app.infrastructure.llm.types import ChatResult, LLMProvider

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "mock_llm_responses"


def test_report_composer_rejects_incomplete_markdown():
    mock_llm = MagicMock()
    mock_llm.chat.return_value = ChatResult(
        text='{"content": "# Incomplete", "confidence_score": 0.5}',
        provider=LLMProvider.GEMINI,
        model="test",
        tokens_in=1,
        tokens_out=1,
    )
    agent = ReportComposerAgent(mock_llm, max_retries=1)
    with pytest.raises(AgentValidationError):
        agent.process({"phase_analyses": [], "markers_analysis": {}, "settings": {"tone": 2}})


def test_report_composer_markdown_output():
    mock_llm = MagicMock()
    payload = json.loads((_FIXTURES / "composer_output.json").read_text(encoding="utf-8"))
    mock_llm.chat.return_value = ChatResult(
        text=json.dumps(payload),
        provider=LLMProvider.GEMINI,
        model="test",
        tokens_in=10,
        tokens_out=20,
    )
    agent = ReportComposerAgent(mock_llm, max_retries=1)
    out = agent.process(
        {
            "phase_analyses": [{"phase_id": "p1", "clinical_narrative": "ok", "confidence_score": 0.9}],
            "markers_analysis": {"emotion_trend": "neutral", "alignment_with_scores": "ok", "confidence_score": 0.8},
            "settings": {"tone": 2},
        }
    )
    assert out["content"].startswith("# Surgical Procedure Evaluation Report")
    assert out["confidence_score"] == 0.91
