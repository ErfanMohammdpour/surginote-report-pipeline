"""Unit tests — LLMCache (PDF §31 step 6)."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from app.application.ai_pipeline.cache import LLMCache, make_cache_key


def test_make_cache_key_stable():
    k1 = make_cache_key(agent="phase_analyzer", user_message='{"phase":"p1"}', model="gemini-2.5-flash", temperature=0.3)
    k2 = make_cache_key(agent="phase_analyzer", user_message='{"phase":"p1"}', model="gemini-2.5-flash", temperature=0.3)
    k3 = make_cache_key(agent="phase_analyzer", user_message='{"phase":"p2"}', model="gemini-2.5-flash", temperature=0.3)
    assert k1 == k2
    assert k1 != k3
    assert len(k1) == 64


def test_cache_miss_then_hit():
    cache = LLMCache(ttl_seconds=3600, enabled=True)
    key = make_cache_key(agent="test", user_message="hello", model="m", temperature=0.1)
    assert cache.get(key) is None
    cache.set(key, "response text")
    assert cache.get(key) == "response text"


def test_cache_disabled_always_miss():
    cache = LLMCache(ttl_seconds=3600, enabled=False)
    key = make_cache_key(agent="test", user_message="hello", model="m", temperature=0.1)
    cache.set(key, "response text")
    assert cache.get(key) is None


def test_cache_ttl_expiry():
    cache = LLMCache(ttl_seconds=1, enabled=True)
    key = make_cache_key(agent="test", user_message="expire", model="m", temperature=0.1)
    cache.set(key, "old")
    with patch("app.application.ai_pipeline.cache.time.time", return_value=time.time() + 2):
        assert cache.get(key) is None


def test_cache_key_changes_with_temperature():
    base = dict(agent="a", user_message="x", model="m")
    k_low = make_cache_key(**base, temperature=0.1)
    k_high = make_cache_key(**base, temperature=0.9)
    assert k_low != k_high


def test_cache_clear():
    cache = LLMCache(ttl_seconds=3600, enabled=True)
    key = make_cache_key(agent="test", user_message="clear", model="m", temperature=0.1)
    cache.set(key, "v")
    cache.clear()
    assert cache.get(key) is None


def test_get_llm_cache_singleton():
    from app.application.ai_pipeline.cache import get_llm_cache, reset_llm_cache_for_tests

    reset_llm_cache_for_tests()
    a = get_llm_cache(ttl_seconds=100, enabled=True)
    b = get_llm_cache()
    assert a is b
    reset_llm_cache_for_tests()
