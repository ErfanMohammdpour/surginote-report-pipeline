"""Shared LLM types — provider tag + chat result."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class LLMProvider(StrEnum):
    """Switch provider via SN_AI_PROVIDER or ai_config.provider."""

    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"

    @classmethod
    def parse(cls, value: str | None, *, default: "LLMProvider | None" = None) -> "LLMProvider":
        if default is None:
            default = cls.GEMINI
        if not value or not str(value).strip():
            return default
        token = str(value).strip().lower()
        aliases = {
            "gpt": cls.OPENAI,
            "chatgpt": cls.OPENAI,
            "gpt-4": cls.OPENAI,
            "gpt-4o": cls.OPENAI,
            "claude": cls.ANTHROPIC,
        }
        if token in aliases:
            return aliases[token]
        try:
            return cls(token)
        except ValueError as exc:
            supported = ", ".join(p.value for p in cls)
            raise ValueError(f"Unknown LLM provider {value!r}. Use one of: {supported}") from exc


DEFAULT_MODEL_BY_PROVIDER: dict[LLMProvider, str] = {
    LLMProvider.GEMINI: "gemini-2.5-flash",
    LLMProvider.OPENAI: "gpt-4o-mini",
    LLMProvider.ANTHROPIC: "claude-3-5-sonnet-latest",
    LLMProvider.OLLAMA: "llama3",
}


@dataclass(frozen=True)
class ChatResult:
    text: str
    provider: LLMProvider
    model: str
    finish_reason: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)
