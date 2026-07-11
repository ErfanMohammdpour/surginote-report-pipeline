from __future__ import annotations

from app.application.ai_pipeline.config import load_ai_pipeline_config
from app.infrastructure.llm.types import LLMProvider

# Re-use infrastructure LLM client tests under ai_pipeline namespace per checklist.


def test_ai_config_provider_tag():
    cfg = load_ai_pipeline_config()
    assert cfg.provider in (LLMProvider.GEMINI, LLMProvider.OPENAI)
