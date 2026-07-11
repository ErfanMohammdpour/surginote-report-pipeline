"""
Unified LLM client — switch provider with one tag.

Usage:
    client = LLMClient.from_settings()                    # SN_AI_PROVIDER=gemini
    client = LLMClient(provider="openai", model="gpt-4o") # per-request override
    result = client.chat(system_prompt="...", user_message="...")
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.infrastructure.llm.providers.anthropic import AnthropicAdapter
from app.infrastructure.llm.providers.gemini import GeminiAdapter
from app.infrastructure.llm.providers.ollama import OllamaAdapter
from app.infrastructure.llm.providers.openai import OpenAIAdapter
from app.infrastructure.llm.types import (
    DEFAULT_MODEL_BY_PROVIDER,
    ChatResult,
    LLMProvider,
)

logger = logging.getLogger(__name__)

_ADAPTER_BY_PROVIDER = {
    LLMProvider.GEMINI: GeminiAdapter,
    LLMProvider.OPENAI: OpenAIAdapter,
    LLMProvider.ANTHROPIC: AnthropicAdapter,
    LLMProvider.OLLAMA: OllamaAdapter,
}


class LLMClient:
    def __init__(
        self,
        *,
        provider: str | LLMProvider | None = None,
        model: str | None = None,
        api_key: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout_seconds: float | None = None,
        fallback_provider: str | LLMProvider | None = None,
    ) -> None:
        self.provider = LLMProvider.parse(
            str(provider) if provider is not None else settings.ai_provider
        )
        self.fallback_provider = (
            LLMProvider.parse(str(fallback_provider))
            if fallback_provider
            else (
                LLMProvider.parse(settings.ai_fallback_provider)
                if settings.ai_fallback_provider
                else None
            )
        )
        self.model = (model or settings.ai_model or DEFAULT_MODEL_BY_PROVIDER[self.provider]).strip()
        self.temperature = float(
            temperature if temperature is not None else settings.ai_temperature
        )
        self.max_tokens = int(max_tokens if max_tokens is not None else settings.ai_max_tokens)
        self.timeout_seconds = float(
            timeout_seconds if timeout_seconds is not None else settings.ai_timeout_seconds
        )
        self._api_key = api_key
        self._adapter = self._build_adapter(self.provider)

    @classmethod
    def from_settings(cls, **overrides: Any) -> LLMClient:
        return cls(**overrides)

    @classmethod
    def from_ai_config(cls, ai_config: dict[str, Any] | None) -> LLMClient:
        cfg = ai_config or {}
        return cls(
            provider=cfg.get("provider"),
            model=cfg.get("model"),
            temperature=cfg.get("temperature"),
            max_tokens=cfg.get("max_tokens"),
        )

    def _build_adapter(self, provider: LLMProvider):
        cls = _ADAPTER_BY_PROVIDER[provider]
        if provider in (LLMProvider.GEMINI, LLMProvider.OPENAI, LLMProvider.ANTHROPIC):
            return cls(api_key=self._api_key)
        if provider is LLMProvider.OLLAMA:
            return OllamaAdapter()
        return cls()

    def chat(
        self,
        *,
        system_prompt: str,
        user_message: str,
        model: str | None = None,
        temperature: float | None = None,
    ) -> ChatResult:
        use_model = (model or self.model).strip()
        use_temp = float(temperature if temperature is not None else self.temperature)
        try:
            result = self._adapter.chat(
                system_prompt=system_prompt,
                user_message=user_message,
                model=use_model,
                temperature=use_temp,
                max_tokens=self.max_tokens,
                timeout_seconds=self.timeout_seconds,
            )
            logger.info(
                "llm_chat provider=%s model=%s tokens_in=%s tokens_out=%s",
                result.provider.value,
                result.model,
                result.tokens_in,
                result.tokens_out,
            )
            return result
        except Exception as primary_exc:
            if not self.fallback_provider or self.fallback_provider == self.provider:
                raise
            logger.warning(
                "llm_primary_failed provider=%s error=%s trying_fallback=%s",
                self.provider.value,
                primary_exc,
                self.fallback_provider.value,
            )
            fallback = self._build_adapter(self.fallback_provider)
            fb_model = DEFAULT_MODEL_BY_PROVIDER[self.fallback_provider]
            return fallback.chat(
                system_prompt=system_prompt,
                user_message=user_message,
                model=fb_model,
                temperature=use_temp,
                max_tokens=self.max_tokens,
                timeout_seconds=self.timeout_seconds,
            )

    def count_tokens(self, text: str) -> int:
        return self._adapter.count_tokens(text)
