from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import register_exception_handlers
from app.domain.errors import (
    AgentError,
    AgentInputError,
    AgentOutputParseError,
    AgentRateLimitError,
    AgentUpstreamError,
    AgentValidationError,
)


@pytest.fixture
def agent_error_client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/agent-error")
    def _agent_error():
        raise AgentError("base agent failure", agent="test_agent")

    @app.get("/agent-validation")
    def _agent_validation():
        raise AgentValidationError(
            "schema fail",
            agent="phase_analyzer",
            errors=[{"path": "confidence_score", "message": "out of range"}],
        )

    @app.get("/agent-input")
    def _agent_input():
        raise AgentInputError("empty phases", agent="data_extractor")

    @app.get("/agent-parse")
    def _agent_parse():
        raise AgentOutputParseError("invalid json", agent="composer")

    @app.get("/agent-rate")
    def _agent_rate():
        raise AgentRateLimitError("429 from provider", agent="llm")

    @app.get("/agent-upstream")
    def _agent_upstream():
        raise AgentUpstreamError("502 from provider", agent="llm")

    return TestClient(app)


@pytest.mark.parametrize(
    "path,status,code",
    [
        ("/agent-error", 400, "agent_error"),
        ("/agent-validation", 422, "agent_validation_error"),
        ("/agent-input", 422, "agent_input_error"),
        ("/agent-parse", 422, "agent_output_parse_error"),
        ("/agent-rate", 429, "agent_rate_limited"),
        ("/agent-upstream", 502, "agent_upstream_error"),
    ],
)
def test_agent_exception_http_mapping(agent_error_client, path, status, code):
    res = agent_error_client.get(path)
    assert res.status_code == status
    body = res.json()
    assert body["code"] == code
    assert "message" in body
    assert "request_id" in body
