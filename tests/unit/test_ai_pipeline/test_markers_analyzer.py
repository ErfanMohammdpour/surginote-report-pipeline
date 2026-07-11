from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from app.application.ai_pipeline.agents.markers_analyzer import MarkersAnalyzerAgent
from app.infrastructure.llm.types import ChatResult, LLMProvider

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def test_markers_analyzer_empty_markers_no_llm():
    mock_llm = MagicMock()
    agent = MarkersAnalyzerAgent(mock_llm)
    out = agent.process({"markers": []})
    assert out["emotion_trend"] == "neutral"
    mock_llm.chat.assert_not_called()


def test_markers_analyzer_with_markers():
    mock_llm = MagicMock()
    payload = json.loads(
        (_FIXTURES / "mock_llm_responses" / "markers_analysis.json").read_text(encoding="utf-8")
    )
    mock_llm.chat.return_value = ChatResult(
        text=json.dumps(payload),
        provider=LLMProvider.GEMINI,
        model="test",
        tokens_in=3,
        tokens_out=4,
    )
    agent = MarkersAnalyzerAgent(mock_llm, max_retries=1)
    s1 = json.loads((_FIXTURES / "annotation_data_full_s1.json").read_text(encoding="utf-8"))
    out = agent.process({"markers": s1["markers"], "scores": s1["scores"]})
    assert out["emotion_trend"] == "mixed"
    assert out["critical_events"]
