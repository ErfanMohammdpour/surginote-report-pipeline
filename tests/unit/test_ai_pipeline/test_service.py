"""Unit tests — merge_ai_config + AI report service."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.schemas import GenerateReportRequest
from app.application.ai_pipeline.config import AIPipelineConfig, load_ai_pipeline_config, merge_ai_config
from app.application.ai_pipeline.schemas import AIConfig
from app.application.ai_pipeline.service import build_orchestrator, run_ai_report
from app.infrastructure.llm.types import LLMProvider

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def _minimal_request() -> GenerateReportRequest:
    data = json.loads((_FIXTURES / "annotation_data_minimal.json").read_text(encoding="utf-8"))
    return GenerateReportRequest.model_validate(data)


def test_merge_ai_config_applies_overrides():
    base = load_ai_pipeline_config()
    merged = merge_ai_config(
        base,
        {
            "temperature": 0.9,
            "enable_review": False,
            "enable_cache": False,
            "provider": "openai",
            "model": "gpt-4o-mini",
            "max_tokens": 1024,
        },
    )
    assert merged.temperature == 0.9
    assert merged.enable_review is False
    assert merged.enable_cache is False
    assert merged.provider == LLMProvider.OPENAI
    assert merged.model == "gpt-4o-mini"
    assert merged.max_tokens == 1024


def test_merge_ai_config_empty_passthrough():
    base = load_ai_pipeline_config()
    assert merge_ai_config(base, {}) is base


def test_build_orchestrator_uses_merged_config():
    req = _minimal_request()
    req.settings.ai_config = AIConfig(
        provider="gemini",
        temperature=0.5,
        enable_review=False,
        enable_cache=True,
    )
    orch = build_orchestrator(req)
    assert orch.config.temperature == 0.5
    assert orch.config.enable_review is False
    assert orch.config.enable_cache is True
    assert orch.llm_client.temperature == 0.5


@pytest.mark.asyncio
async def test_run_ai_report_delegates_to_orchestrator():
    req = _minimal_request()
    fake_result = {
        "content": "# Surgical Procedure Evaluation Report\n",
        "generatedAt": "2026-01-01T00:00:00Z",
        "metadata": {"fallback_used": False, "cache_hits": 0},
    }
    mock_orch = MagicMock()
    mock_orch.run = AsyncMock(return_value=fake_result)
    with patch("app.application.ai_pipeline.service.build_orchestrator", return_value=mock_orch):
        result = await run_ai_report(req)
    assert result == fake_result
    mock_orch.run.assert_awaited_once()
