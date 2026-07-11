"""OpenAI Chat Completions adapter (GPT / ChatGPT)."""

from __future__ import annotations

import os
from typing import Any

import httpx

from app.infrastructure.llm.types import ChatResult, LLMProvider


class OpenAIError(Exception):
    def __init__(self, status_code: int, body: str):
        super().__init__(f"OpenAI HTTP {status_code}: {body[:500]}")
        self.status_code = status_code
        self.body = body


def resolve_openai_api_key(explicit: str | None = None) -> str | None:
    if explicit and explicit.strip():
        return explicit.strip()
    for env_name in ("OPENAI_API_KEY", "SN_OPENAI_API_KEY"):
        hit = os.environ.get(env_name, "").strip()
        if hit:
            return hit
    return None


class OpenAIAdapter:
    provider = LLMProvider.OPENAI

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = resolve_openai_api_key(api_key)

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
            raise ValueError("openai_api_key_missing")
        url = "https://api.openai.com/v1/chat/completions"
        payload: dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=timeout_seconds) as client:
            r = client.post(url, headers=headers, json=payload)
        if r.status_code >= 400:
            raise OpenAIError(r.status_code, r.text)
        data = r.json()
        choices = data.get("choices") or []
        text = ""
        finish_reason = None
        if choices:
            msg = choices[0].get("message") or {}
            text = str(msg.get("content") or "").strip()
            finish_reason = choices[0].get("finish_reason")
        usage = data.get("usage") or {}
        return ChatResult(
            text=text,
            provider=self.provider,
            model=model,
            finish_reason=finish_reason,
            tokens_in=int(usage.get("prompt_tokens") or 0) or None,
            tokens_out=int(usage.get("completion_tokens") or 0) or None,
            raw=data,
        )

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)
