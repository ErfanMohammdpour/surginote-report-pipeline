"""Shared helpers for LLM JSON parsing, validation, and retries."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel, ValidationError as PydanticValidationError

from app.domain.errors import AgentOutputParseError, AgentValidationError

T = TypeVar("T")

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def parse_json_from_llm(text: str) -> dict:
    """Extract JSON object from raw LLM text (handles fences and wrapped prose)."""
    if not text or not str(text).strip():
        raise AgentOutputParseError("LLM returned empty response", agent="parser")

    cleaned = str(text).strip()
    fence = _JSON_FENCE_RE.search(cleaned)
    if fence:
        cleaned = fence.group(1).strip()

    candidates = [cleaned]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start >= 0 and end > start:
        candidates.append(cleaned[start : end + 1])

    last_err: Exception | None = None
    for candidate in candidates:
        for payload in (candidate, _TRAILING_COMMA_RE.sub(r"\1", candidate)):
            try:
                data = json.loads(payload)
            except json.JSONDecodeError as exc:
                last_err = exc
                continue
            if isinstance(data, dict):
                return data
            raise AgentOutputParseError("LLM JSON root must be an object", agent="parser")
    raise AgentOutputParseError(f"Invalid LLM JSON: {last_err}", agent="parser")


def validate_llm_output(model: type[BaseModel], data: dict, *, agent: str | None = None) -> BaseModel:
    try:
        return model.model_validate(data)
    except PydanticValidationError as exc:
        errors = [
            {"path": ".".join(str(x) for x in e.get("loc", ())), "message": e.get("msg", "")}
            for e in exc.errors()
        ]
        raise AgentValidationError(
            f"LLM output failed schema validation for {model.__name__}",
            agent=agent,
            errors=errors,
        ) from exc


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    max_attempts: int = 3,
    base_delay_seconds: float = 1.0,
) -> T:
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt >= max_attempts - 1:
                raise
            time.sleep(base_delay_seconds * (2**attempt))
    if last_exc:
        raise last_exc
    raise RuntimeError("retry_with_backoff exhausted without exception")
