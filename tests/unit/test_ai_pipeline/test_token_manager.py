"""Unit tests — TokenManager (PDF §31 step 6)."""

from __future__ import annotations

import pytest

from app.application.ai_pipeline.token_manager import TokenBudget, TokenManager


def test_count_empty_and_text():
    tm = TokenManager()
    assert tm.count("") == 0
    assert tm.count("abcd") == 1
    assert tm.count("a" * 40) == 10


def test_chunk_splits_long_text():
    tm = TokenManager(chars_per_token=4)
    text = "word " * 50  # ~250 chars → ~62 tokens
    chunks = tm.chunk(text, max_tokens=10)
    assert len(chunks) >= 5
    assert "".join(chunks).replace(" ", "") == text.replace(" ", "")


def test_chunk_single_short_piece():
    tm = TokenManager()
    text = "short prompt"
    assert tm.chunk(text, max_tokens=100) == [text]


def test_check_budget_under_limit():
    tm = TokenManager(chars_per_token=4)
    budget = tm.check_budget("hello world", max_tokens=100)
    assert isinstance(budget, TokenBudget)
    assert budget.token_count == 2
    assert budget.over_limit is False
    assert budget.should_warn is False


def test_check_budget_warn_threshold():
    tm = TokenManager(chars_per_token=4, warn_ratio=0.5)
    budget = tm.check_budget("a" * 40, max_tokens=10)  # 10 tokens = at limit
    assert budget.should_warn is True
    assert budget.over_limit is False


def test_check_budget_over_limit():
    tm = TokenManager(chars_per_token=4)
    budget = tm.check_budget("a" * 80, max_tokens=10)
    assert budget.over_limit is True


def test_estimate_chat_tokens():
    tm = TokenManager()
    tin, tout = tm.estimate_chat_tokens(system_prompt="sys", user_message="user msg", response="out")
    assert tin >= 1
    assert tout >= 1
