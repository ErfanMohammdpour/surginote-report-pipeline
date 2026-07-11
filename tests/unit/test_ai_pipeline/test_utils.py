from __future__ import annotations

import pytest

from app.application.ai_pipeline.utils import (
    parse_json_from_llm,
    retry_with_backoff,
    validate_llm_output,
)
from app.application.ai_pipeline.schemas import PhaseAnalysisOutput
from app.domain.errors import AgentOutputParseError, AgentValidationError


def test_parse_json_from_llm_plain():
    data = parse_json_from_llm('{"phase_id": "p1", "ok": true}')
    assert data["phase_id"] == "p1"


def test_parse_json_from_llm_markdown_fence():
    raw = 'Here is JSON:\n```json\n{"a": 1}\n```'
    assert parse_json_from_llm(raw)["a"] == 1


def test_parse_json_from_llm_trailing_comma():
    raw = '{"items": [1, 2,], "ok": true,}'
    data = parse_json_from_llm(raw)
    assert data["items"] == [1, 2]


def test_parse_json_from_llm_empty_raises():
    with pytest.raises(AgentOutputParseError):
        parse_json_from_llm("   ")


def test_validate_llm_output_success():
    out = validate_llm_output(
        PhaseAnalysisOutput,
        {
            "phase_id": "p1",
            "clinical_narrative": "Good technique.",
            "confidence_score": 0.8,
        },
        agent="phase_analyzer",
    )
    assert out.phase_id == "p1"


def test_validate_llm_output_schema_fail():
    with pytest.raises(AgentValidationError) as exc_info:
        validate_llm_output(
            PhaseAnalysisOutput,
            {"phase_id": "p1", "clinical_narrative": "x", "confidence_score": 9},
            agent="phase_analyzer",
        )
    assert exc_info.value.errors
    assert exc_info.value.agent == "phase_analyzer"


def test_retry_with_backoff_succeeds_second_attempt():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("transient")
        return "ok"

    assert retry_with_backoff(flaky, max_attempts=3, base_delay_seconds=0) == "ok"


def test_retry_with_backoff_exhaust_raises():
    def always_fail():
        raise ValueError("nope")

    with pytest.raises(ValueError, match="nope"):
        retry_with_backoff(always_fail, max_attempts=2, base_delay_seconds=0)
