"""Shared LLM mock helpers for ai_pipeline tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.infrastructure.llm.types import ChatResult, LLMProvider

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "mock_llm_responses"


def load_mock(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def chat_json(payload: dict, *, tokens_in: int = 10, tokens_out: int = 15) -> ChatResult:
    return ChatResult(
        text=json.dumps(payload),
        provider=LLMProvider.GEMINI,
        model="test",
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )


def make_scenario_llm(*, fail_phase: str | None = None, review_approved: bool = True) -> MagicMock:
    llm = MagicMock()
    composer_calls = {"n": 0}

    def chat(**kwargs):
        system_prompt = (kwargs.get("system_prompt") or "").lower()
        user_message = kwargs.get("user_message") or ""

        if "quality assurance reviewer" in system_prompt:
            name = "quality_review_approved.json" if review_approved else "quality_review_rejected.json"
            return chat_json(load_mock(name))

        if "senior surgical report composer" in system_prompt:
            composer_calls["n"] += 1
            return chat_json(load_mock("composer_output.json"))

        if "clinical annotator analyzer" in system_prompt:
            return chat_json(load_mock("markers_analysis.json"))

        if "board-certified ophthalmology" in system_prompt:
            if fail_phase and fail_phase in user_message:
                raise RuntimeError(f"phase analyzer failed for {fail_phase}")
            for phase_key, fixture in (
                ("phase_rhexis", "phase_analysis_rhexis.json"),
                ("phase_phaco", "phase_analysis_phaco.json"),
                ("phase_ia", "phase_analysis_ia.json"),
            ):
                if phase_key in user_message:
                    return chat_json(load_mock(fixture))
            return chat_json(load_mock("phase_analysis_rhexis.json"))

        if "surgical annotation data normalizer" in system_prompt:
            return chat_json(load_mock("data_extractor_ok.json"))

        raise RuntimeError(f"unexpected LLM call: {system_prompt[:80]}")

    llm.chat.side_effect = chat
    llm.model = "gemini-2.5-flash"
    llm._composer_calls = composer_calls
    return llm


@pytest.fixture(autouse=True)
def _reset_llm_cache():
    from app.application.ai_pipeline.cache import reset_llm_cache_for_tests

    reset_llm_cache_for_tests()
    yield
    reset_llm_cache_for_tests()
