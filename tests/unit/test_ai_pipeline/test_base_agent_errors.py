from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from app.application.ai_pipeline.base_agent import BaseAgent
from app.application.ai_pipeline.schemas import PhaseAnalysisOutput
from app.domain.errors import AgentRateLimitError, AgentUpstreamError
from app.infrastructure.llm.gemini_rest import GeminiError
from app.infrastructure.llm.llm_client import LLMClient


class _ProbeAgent(BaseAgent):
    output_model = PhaseAnalysisOutput

    def process(self, input_data):  # type: ignore[no-untyped-def]
        return self._call_llm("probe")


def test_base_agent_maps_gemini_429_to_rate_limit():
    mock_llm = MagicMock()
    mock_llm.chat.side_effect = GeminiError(429, "rate limited")
    agent = _ProbeAgent(
        agent_name="probe",
        prompt_file="phase_analysis.txt",
        llm_client=mock_llm,
        max_retries=1,
    )
    with pytest.raises(AgentRateLimitError):
        agent.process({})


def test_base_agent_maps_gemini_502_to_upstream():
    mock_llm = MagicMock()
    mock_llm.chat.side_effect = GeminiError(502, "bad gateway")
    agent = _ProbeAgent(
        agent_name="probe",
        prompt_file="phase_analysis.txt",
        llm_client=mock_llm,
        max_retries=1,
    )
    with pytest.raises(AgentUpstreamError):
        agent.process({})


def test_phase_analyzer_missing_phase_id_raises_input_error():
    from app.application.ai_pipeline.agents.phase_analyzer import PhaseAnalyzerAgent
    from app.domain.errors import AgentInputError

    agent = PhaseAnalyzerAgent(MagicMock())
    with pytest.raises(AgentInputError):
        agent.process({"phase": {}})
