from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.application.ai_pipeline.agents.data_extractor import DataExtractorAgent
from app.infrastructure.llm.types import ChatResult, LLMProvider

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
_S1 = _FIXTURES / "annotation_data_full_s1.json"


def _chat(text: str) -> ChatResult:
    return ChatResult(text=text, provider=LLMProvider.GEMINI, model="test", tokens_in=1, tokens_out=2)


@pytest.fixture
def mock_llm():
    return MagicMock()


def test_data_extractor_normalizes_s1_without_llm(mock_llm):
    data = json.loads(_S1.read_text(encoding="utf-8"))
    agent = DataExtractorAgent(mock_llm)
    out = agent.process(data)
    assert "error" not in out
    assert len(out["normalized_phases"]) == 3
    assert out["normalized_markers"][0]["timestamp"] <= out["normalized_markers"][-1]["timestamp"]
    mock_llm.chat.assert_not_called()


def test_data_extractor_invalid_empty_phases(mock_llm):
    agent = DataExtractorAgent(mock_llm)
    out = agent.process({"phases": []})
    assert out["error"]
    assert out["normalized"] is None


def test_data_extractor_llm_path_when_forced(mock_llm):
    mock_llm.chat.return_value = _chat(
        (_FIXTURES / "mock_llm_responses" / "data_extractor_ok.json").read_text(encoding="utf-8")
    )
    data = json.loads(_S1.read_text(encoding="utf-8"))
    data["force_llm_normalize"] = True
    agent = DataExtractorAgent(mock_llm, max_retries=1)
    out = agent.process(data)
    assert out["normalized_phases"]
    mock_llm.chat.assert_called_once()
