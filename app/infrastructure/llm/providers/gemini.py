"""Gemini adapter — wraps existing gemini_rest."""

from __future__ import annotations

from app.config import resolve_gemini_api_key
from app.infrastructure.llm.gemini_rest import GeminiError, generate_content
from app.infrastructure.llm.types import ChatResult, LLMProvider


class GeminiAdapter:
    provider = LLMProvider.GEMINI

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = (api_key or resolve_gemini_api_key() or "").strip()

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
        if not self._api_key:
            raise ValueError("gemini_api_key_missing")
        res = generate_content(
            api_key=self._api_key,
            model=model,
            system_instruction=system_prompt,
            user_message=user_message,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
        )
        usage = (res.get("raw") or {}).get("usageMetadata") or {}
        return ChatResult(
            text=res["text"],
            provider=self.provider,
            model=model,
            finish_reason=res.get("finish_reason"),
            tokens_in=int(usage.get("promptTokenCount") or 0) or None,
            tokens_out=int(usage.get("candidatesTokenCount") or 0) or None,
            raw=res.get("raw") or {},
        )

    def count_tokens(self, text: str) -> int:
        # Rough estimate until dedicated tokenizer wired in token_manager.
        return max(1, len(text) // 4)


__all__ = ["GeminiAdapter", "GeminiError"]
