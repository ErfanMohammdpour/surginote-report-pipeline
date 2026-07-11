"""Provider adapter protocol."""

from __future__ import annotations

from typing import Protocol

from app.infrastructure.llm.types import ChatResult, LLMProvider


class LLMProviderAdapter(Protocol):
    provider: LLMProvider

    def chat(
        self,
        *,
        system_prompt: str,
        user_message: str,
        model: str,
        temperature: float,
        max_tokens: int,
        timeout_seconds: float,
    ) -> ChatResult: ...

    def count_tokens(self, text: str) -> int: ...
