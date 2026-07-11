"""Anthropic adapter — stub for Phase 1; same interface as Gemini/OpenAI."""

from __future__ import annotations

from app.infrastructure.llm.types import ChatResult, LLMProvider


class AnthropicAdapter:
    provider = LLMProvider.ANTHROPIC

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def chat(
        self,
        *,
        system_prompt: str,
        user_message: str,
        model: str,
        temperature: float,
        max_tokens: int,
        timeout_seconds: float,
    ) -> ChatResult:
        raise NotImplementedError(
            "Anthropic provider not wired yet. Set SN_AI_PROVIDER=gemini or openai."
        )

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)
