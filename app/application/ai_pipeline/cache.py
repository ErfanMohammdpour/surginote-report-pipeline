"""In-memory LLM response cache — SHA-256 key, TTL expiry."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass


def make_cache_key(
    *,
    agent: str,
    user_message: str,
    model: str,
    temperature: float,
) -> str:
    """Stable cache key: agent + input + model + temperature."""
    payload = f"{agent}|{model}|{temperature:.4f}|{user_message}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class _CacheEntry:
    value: str
    expires_at: float


class LLMCache:
    """Thread-unsafe in-process cache suitable for single-worker deployments."""

    def __init__(self, *, ttl_seconds: int = 3600, enabled: bool = True) -> None:
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.enabled = bool(enabled)
        self._store: dict[str, _CacheEntry] = {}

    def get(self, key: str) -> str | None:
        if not self.enabled:
            return None
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() > entry.expires_at:
            del self._store[key]
            return None
        return entry.value

    def set(self, key: str, value: str) -> None:
        if not self.enabled:
            return
        self._store[key] = _CacheEntry(
            value=value,
            expires_at=time.time() + self.ttl_seconds,
        )

    def clear(self) -> None:
        self._store.clear()


_shared_cache: LLMCache | None = None


def get_llm_cache(*, ttl_seconds: int | None = None, enabled: bool | None = None) -> LLMCache:
    """Process-wide cache reused across API requests (same worker)."""
    global _shared_cache
    if _shared_cache is None:
        _shared_cache = LLMCache(
            ttl_seconds=ttl_seconds or 3600,
            enabled=True if enabled is None else bool(enabled),
        )
    if ttl_seconds is not None:
        _shared_cache.ttl_seconds = max(1, int(ttl_seconds))
    if enabled is not None:
        _shared_cache.enabled = bool(enabled)
    return _shared_cache


def reset_llm_cache_for_tests() -> None:
    """Clear singleton — test isolation only."""
    global _shared_cache
    if _shared_cache is not None:
        _shared_cache.clear()
    _shared_cache = None
