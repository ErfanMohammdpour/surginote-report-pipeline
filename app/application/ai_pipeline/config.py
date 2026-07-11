"""AI pipeline configuration — reads SN_AI_* from app settings."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from app.config import settings
from app.infrastructure.llm.types import DEFAULT_MODEL_BY_PROVIDER, LLMProvider


@dataclass(frozen=True)
class AIPipelineConfig:
    provider: LLMProvider
    fallback_provider: LLMProvider | None
    model: str
    temperature: float
    max_tokens: int
    timeout_seconds: float
    enable_cache: bool
    cache_ttl_seconds: int
    enable_review: bool
    max_parallel: int
    max_retries: int


def load_ai_pipeline_config() -> AIPipelineConfig:
    provider = LLMProvider.parse(settings.ai_provider)
    fallback = (
        LLMProvider.parse(settings.ai_fallback_provider)
        if settings.ai_fallback_provider
        else None
    )
    model = (settings.ai_model or DEFAULT_MODEL_BY_PROVIDER[provider]).strip()
    return AIPipelineConfig(
        provider=provider,
        fallback_provider=fallback,
        model=model,
        temperature=float(settings.ai_temperature),
        max_tokens=int(settings.ai_max_tokens),
        timeout_seconds=float(settings.ai_timeout_seconds),
        enable_cache=bool(settings.ai_enable_cache),
        cache_ttl_seconds=int(settings.ai_cache_ttl_seconds),
        enable_review=bool(settings.ai_enable_review),
        max_parallel=int(settings.ai_max_parallel),
        max_retries=int(settings.ai_max_retries),
    )


def merge_ai_config(base: AIPipelineConfig, ai_config: dict[str, Any] | None) -> AIPipelineConfig:
    """Apply per-request ai_config overrides onto env-backed defaults."""
    if not ai_config:
        return base
    updates: dict[str, Any] = {}
    if ai_config.get("provider") is not None:
        updates["provider"] = LLMProvider.parse(str(ai_config["provider"]))
    if ai_config.get("model") is not None:
        updates["model"] = str(ai_config["model"]).strip()
    if ai_config.get("temperature") is not None:
        updates["temperature"] = float(ai_config["temperature"])
    if ai_config.get("max_tokens") is not None:
        updates["max_tokens"] = int(ai_config["max_tokens"])
    if ai_config.get("enable_review") is not None:
        updates["enable_review"] = bool(ai_config["enable_review"])
    if ai_config.get("enable_cache") is not None:
        updates["enable_cache"] = bool(ai_config["enable_cache"])
    return replace(base, **updates) if updates else base
