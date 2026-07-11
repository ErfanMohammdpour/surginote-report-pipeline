"""Unit tests — merge_ai_config."""

from __future__ import annotations

from app.application.ai_pipeline.config import load_ai_pipeline_config, merge_ai_config
from app.infrastructure.llm.types import LLMProvider


def test_merge_ai_config_provider_and_flags():
    base = load_ai_pipeline_config()
    merged = merge_ai_config(base, {"provider": "openai", "enable_cache": False})
    assert merged.provider == LLMProvider.OPENAI
    assert merged.enable_cache is False
