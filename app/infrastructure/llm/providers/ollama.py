"""Ollama local adapter — stub for Phase 1."""

from __future__ import annotations

from app.infrastructure.llm.types import ChatResult, LLMProvider


class OllamaAdapter:
    provider = LLMProvider.OLLAMA

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or "http://localhost:11434").rstrip("/")

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
            "Ollama provider not wired yet. Set SN_AI_PROVIDER=gemini or openai."
        )

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)
