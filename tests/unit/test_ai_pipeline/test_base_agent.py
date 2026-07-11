from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.application.ai_pipeline.base_agent import BaseAgent
from app.application.ai_pipeline.schemas import PhaseAnalysisOutput
from app.domain.errors import AgentUpstreamError
from app.infrastructure.llm.llm_client import LLMClient
from app.infrastructure.llm.types import ChatResult, LLMProvider


class _EchoAgent(BaseAgent):
    output_model = PhaseAnalysisOutput

    def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return self._call_llm_json(input_data)


def _chat_result(text: str) -> ChatResult:
    return ChatResult(
        text=text,
        provider=LLMProvider.GEMINI,
        model="gemini-2.5-flash",
        tokens_in=10,
        tokens_out=20,
    )


def test_base_agent_loads_prompt_file():
    mock_client = MagicMock(spec=LLMClient)
    agent = _EchoAgent(
        agent_name="phase_analyzer",
        prompt_file="phase_analysis.txt",
        llm_client=mock_client,
    )
    assert "board-certified ophthalmology" in agent.system_prompt.lower()


def test_base_agent_call_llm_returns_text():
    mock_client = MagicMock(spec=LLMClient)
    mock_client.chat.return_value = _chat_result("hello")
    agent = _EchoAgent(
        agent_name="test",
        prompt_file="phase_analysis.txt",
        llm_client=mock_client,
        max_retries=1,
    )
    assert agent._call_llm("payload") == "hello"
    mock_client.chat.assert_called_once()


def test_base_agent_retries_then_raises_upstream():
    mock_client = MagicMock(spec=LLMClient)
    mock_client.chat.side_effect = RuntimeError("down")
    agent = _EchoAgent(
        agent_name="test",
        prompt_file="phase_analysis.txt",
        llm_client=mock_client,
        max_retries=2,
    )
    with pytest.raises(AgentUpstreamError):
        agent._call_llm("payload")
    assert mock_client.chat.call_count == 2


def test_base_agent_call_llm_json_validates_schema():
    mock_client = MagicMock(spec=LLMClient)
    mock_client.chat.return_value = _chat_result(
        '{"phase_id":"p1","clinical_narrative":"Solid work.","confidence_score":0.9}'
    )
    agent = _EchoAgent(
        agent_name="phase_analyzer",
        prompt_file="phase_analysis.txt",
        llm_client=mock_client,
        max_retries=1,
    )
    out = agent.process({"phase_id": "p1"})
    assert out["phase_id"] == "p1"
    assert out["confidence_score"] == 0.9


def test_base_agent_cache_hit_skips_llm():
    from app.application.ai_pipeline.cache import LLMCache

    mock_client = MagicMock(spec=LLMClient)
    mock_client.model = "gemini-2.5-flash"
    mock_client.provider = LLMProvider.GEMINI
    cache = LLMCache(ttl_seconds=3600, enabled=True)
    agent = _EchoAgent(
        agent_name="test",
        prompt_file="phase_analysis.txt",
        llm_client=mock_client,
        max_retries=1,
        cache=cache,
    )
    mock_client.chat.return_value = _chat_result("cached-body")
    assert agent._call_llm("payload") == "cached-body"
    assert mock_client.chat.call_count == 1
    assert agent._call_llm("payload") == "cached-body"
    assert mock_client.chat.call_count == 1
    assert agent.last_cache_hit is True
    assert agent.last_chat is not None
    assert agent.last_chat.tokens_in == 0


def test_base_agent_estimates_missing_token_counts():
    mock_client = MagicMock(spec=LLMClient)
    mock_client.chat.return_value = ChatResult(
        text="hello",
        provider=LLMProvider.GEMINI,
        model="gemini-2.5-flash",
        tokens_in=None,
        tokens_out=None,
    )
    agent = _EchoAgent(
        agent_name="test",
        prompt_file="phase_analysis.txt",
        llm_client=mock_client,
        max_retries=1,
    )
    agent._call_llm("payload")
    assert agent.last_chat is not None
    assert agent.last_chat.tokens_in is not None
    assert agent.last_chat.tokens_out is not None
