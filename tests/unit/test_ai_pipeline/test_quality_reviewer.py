from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from app.application.ai_pipeline.agents.quality_reviewer import QualityReviewerAgent
from app.infrastructure.llm.types import ChatResult, LLMProvider

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "mock_llm_responses"


def test_quality_reviewer_approved():
    mock_llm = MagicMock()
    payload = json.loads((_FIXTURES / "quality_review_approved.json").read_text(encoding="utf-8"))
    mock_llm.chat.return_value = ChatResult(
        text=json.dumps(payload),
        provider=LLMProvider.GEMINI,
        model="test",
        tokens_in=2,
        tokens_out=3,
    )
    agent = QualityReviewerAgent(mock_llm, max_retries=1)
    out = agent.process({"report": "# Report", "settings": {"tone": 2}})
    assert out["approved"] is True


def test_quality_reviewer_rejected():
    mock_llm = MagicMock()
    payload = json.loads((_FIXTURES / "quality_review_rejected.json").read_text(encoding="utf-8"))
    mock_llm.chat.return_value = ChatResult(
        text=json.dumps(payload),
        provider=LLMProvider.GEMINI,
        model="test",
        tokens_in=2,
        tokens_out=3,
    )
    agent = QualityReviewerAgent(mock_llm, max_retries=1)
    out = agent.process({"report": "# Report", "settings": {"tone": 2}})
    assert out["approved"] is False
    assert out["suggested_fixes"]
