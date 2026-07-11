"""Abstract base for all AI pipeline agents."""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import replace
from pathlib import Path
from typing import Any

from app.application.ai_pipeline.cache import LLMCache, make_cache_key
from app.application.ai_pipeline.token_manager import TokenManager
from app.application.ai_pipeline.utils import parse_json_from_llm, validate_llm_output
from app.domain.errors import AgentRateLimitError, AgentUpstreamError
from app.infrastructure.llm.llm_client import LLMClient
from app.infrastructure.llm.types import ChatResult
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


class BaseAgent(ABC):
    """Load prompt from txt, call LLM with retries, return structured output."""

    output_model: type[BaseModel] | None = None

    def __init__(
        self,
        *,
        agent_name: str,
        prompt_file: str,
        llm_client: LLMClient,
        temperature: float = 0.3,
        max_retries: int = 2,
        cache: LLMCache | None = None,
        token_manager: TokenManager | None = None,
        max_tokens: int | None = None,
        enable_cache: bool | None = None,
    ) -> None:
        self.agent_name = agent_name
        self.llm_client = llm_client
        self.temperature = temperature
        self.max_retries = max_retries
        self.cache = cache
        self.token_manager = token_manager or TokenManager()
        self.max_tokens = max_tokens
        self.enable_cache = enable_cache
        self.system_prompt = self._load_prompt(prompt_file)
        self.last_chat: ChatResult | None = None
        self.last_latency_ms: int = 0
        self.last_cache_hit = False
        self.cache_hits = 0

    @staticmethod
    def _load_prompt(filename: str) -> str:
        path = _PROMPTS_DIR / filename
        if not path.is_file():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        return path.read_text(encoding="utf-8")

    def _cache_enabled(self) -> bool:
        if self.cache is None:
            return False
        if self.enable_cache is not None:
            return bool(self.enable_cache)
        return self.cache.enabled

    def _call_llm(self, user_message: str) -> str:
        self.last_cache_hit = False
        cache_key: str | None = None
        if self._cache_enabled():
            cache_key = make_cache_key(
                agent=self.agent_name,
                user_message=user_message,
                model=self.llm_client.model,
                temperature=self.temperature,
            )
            cached = self.cache.get(cache_key)  # type: ignore[union-attr]
            if cached is not None:
                self.last_cache_hit = True
                self.cache_hits += 1
                self.last_chat = ChatResult(
                    text=cached,
                    provider=self.llm_client.provider,
                    model=self.llm_client.model,
                    tokens_in=0,
                    tokens_out=0,
                )
                logger.info(
                    "agent=%s cache_hit=true latency_ms=0 tokens_in=0 tokens_out=0",
                    self.agent_name,
                )
                return cached

        if self.max_tokens:
            prompt_blob = f"{self.system_prompt}\n{user_message}"
            self.token_manager.warn_if_over_budget(
                prompt_blob,
                self.max_tokens,
                agent=self.agent_name,
            )

        last_exc: Exception | None = None
        attempts = max(1, self.max_retries)
        for attempt in range(attempts):
            started = time.perf_counter()
            try:
                result = self.llm_client.chat(
                    system_prompt=self.system_prompt,
                    user_message=user_message,
                    temperature=self.temperature,
                )
                if result.tokens_in is None or result.tokens_out is None:
                    est_in, est_out = self.token_manager.estimate_chat_tokens(
                        system_prompt=self.system_prompt,
                        user_message=user_message,
                        response=result.text,
                    )
                    result = replace(
                        result,
                        tokens_in=result.tokens_in if result.tokens_in is not None else est_in,
                        tokens_out=result.tokens_out if result.tokens_out is not None else est_out,
                    )
                self.last_chat = result
                self.last_latency_ms = int((time.perf_counter() - started) * 1000)
                if cache_key and self.cache is not None:
                    self.cache.set(cache_key, result.text)
                logger.info(
                    "agent=%s attempt=%d latency_ms=%d tokens_in=%s tokens_out=%s provider=%s cache_hit=false",
                    self.agent_name,
                    attempt + 1,
                    self.last_latency_ms,
                    result.tokens_in,
                    result.tokens_out,
                    result.provider.value,
                )
                return result.text
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "agent=%s attempt=%d failed error=%s",
                    self.agent_name,
                    attempt + 1,
                    exc,
                )
                if attempt >= attempts - 1:
                    raise self._translate_llm_error(exc) from exc
        raise AgentUpstreamError("LLM call failed", agent=self.agent_name) from last_exc

    @staticmethod
    def _translate_llm_error(exc: Exception) -> Exception:
        from app.infrastructure.llm.gemini_rest import GeminiError
        from app.infrastructure.llm.providers.openai import OpenAIError

        if isinstance(exc, (AgentUpstreamError, AgentRateLimitError)):
            return exc
        if isinstance(exc, GeminiError):
            if exc.status_code == 429:
                return AgentRateLimitError(
                    f"Gemini rate limited: {exc.status_code}",
                    agent="llm",
                )
            return AgentUpstreamError(
                f"Gemini upstream error: {exc.status_code}",
                agent="llm",
            )
        if isinstance(exc, OpenAIError):
            if exc.status_code == 429:
                return AgentRateLimitError(
                    f"OpenAI rate limited: {exc.status_code}",
                    agent="llm",
                )
            return AgentUpstreamError(
                f"OpenAI upstream error: {exc.status_code}",
                agent="llm",
            )
        return AgentUpstreamError(str(exc), agent="llm")

    def _call_llm_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw = self._call_llm(json.dumps(payload, ensure_ascii=False, indent=2))
        data = parse_json_from_llm(raw)
        if self.output_model is not None:
            validated = validate_llm_output(self.output_model, data, agent=self.agent_name)
            return validated.model_dump()
        return data

    @abstractmethod
    def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Run agent logic and return JSON-serializable output."""
