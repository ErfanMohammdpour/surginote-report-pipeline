"""Token counting and prompt chunking for LLM budget checks."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TokenBudget:
    token_count: int
    max_tokens: int
    over_limit: bool
    should_warn: bool


class TokenManager:
    """Lightweight token estimator (chars/4) until provider-native counting is wired."""

    def __init__(self, *, chars_per_token: int = 4, warn_ratio: float = 0.85) -> None:
        self.chars_per_token = max(1, int(chars_per_token))
        self.warn_ratio = min(1.0, max(0.0, float(warn_ratio)))

    def count(self, text: str) -> int:
        if not text:
            return 0
        return max(1, len(text) // self.chars_per_token)

    def chunk(self, text: str, *, max_tokens: int) -> list[str]:
        if max_tokens <= 0:
            return [text] if text else []
        max_chars = max_tokens * self.chars_per_token
        if len(text) <= max_chars:
            return [text]

        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + max_chars)
            if end < len(text):
                split = text.rfind(" ", start, end)
                if split > start:
                    end = split
            piece = text[start:end].strip()
            if piece:
                chunks.append(piece)
            start = end if end > start else start + max_chars
        return chunks or [text]

    def check_budget(self, text: str, max_tokens: int) -> TokenBudget:
        token_count = self.count(text)
        warn_at = int(max_tokens * self.warn_ratio)
        return TokenBudget(
            token_count=token_count,
            max_tokens=max_tokens,
            over_limit=token_count > max_tokens,
            should_warn=token_count >= warn_at,
        )

    def estimate_chat_tokens(
        self,
        *,
        system_prompt: str,
        user_message: str,
        response: str,
    ) -> tuple[int, int]:
        prompt_text = f"{system_prompt}\n{user_message}"
        return self.count(prompt_text), self.count(response)

    def warn_if_over_budget(self, text: str, max_tokens: int, *, agent: str) -> None:
        budget = self.check_budget(text, max_tokens)
        if budget.over_limit:
            logger.warning(
                "agent=%s token_budget exceeded count=%d max=%d",
                agent,
                budget.token_count,
                budget.max_tokens,
            )
        elif budget.should_warn:
            logger.info(
                "agent=%s token_budget warn count=%d max=%d",
                agent,
                budget.token_count,
                budget.max_tokens,
            )
