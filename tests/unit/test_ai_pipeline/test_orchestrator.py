from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.application.ai_pipeline.config import AIPipelineConfig
from app.application.ai_pipeline.orchestrator import PipelineOrchestrator
from app.infrastructure.llm.types import ChatResult, LLMProvider

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
_S1 = _FIXTURES / "annotation_data_full_s1.json"
_MOCK = _FIXTURES / "mock_llm_responses"


def _load(name: str) -> dict:
    return json.loads((_MOCK / name).read_text(encoding="utf-8"))


def _chat_json(payload: dict) -> ChatResult:
    return ChatResult(
        text=json.dumps(payload),
        provider=LLMProvider.GEMINI,
        model="test",
        tokens_in=10,
        tokens_out=15,
    )


def _cfg(**overrides) -> AIPipelineConfig:
    base = dict(
        provider=LLMProvider.GEMINI,
        fallback_provider=None,
        model="gemini-2.5-flash",
        temperature=0.3,
        max_tokens=2048,
        timeout_seconds=60.0,
        enable_cache=False,
        cache_ttl_seconds=3600,
        enable_review=True,
        max_parallel=4,
        max_retries=1,
    )
    base.update(overrides)
    return AIPipelineConfig(**base)


def _make_llm(*, fail_phase: str | None = None, review_approved: bool = True) -> MagicMock:
    llm = MagicMock()
    phase_calls = {"n": 0}
    composer_calls = {"n": 0}

    def chat(**kwargs):
        system_prompt = (kwargs.get("system_prompt") or "").lower()
        user_message = kwargs.get("user_message") or ""

        if "quality assurance reviewer" in system_prompt:
            name = "quality_review_approved.json" if review_approved else "quality_review_rejected.json"
            return _chat_json(_load(name))

        if "senior surgical report composer" in system_prompt:
            composer_calls["n"] += 1
            return _chat_json(_load("composer_output.json"))

        if "clinical annotator analyzer" in system_prompt:
            return _chat_json(_load("markers_analysis.json"))

        if "board-certified ophthalmology" in system_prompt:
            phase_calls["n"] += 1
            if fail_phase and fail_phase in user_message:
                raise RuntimeError(f"phase analyzer failed for {fail_phase}")
            if "phase_rhexis" in user_message:
                return _chat_json(_load("phase_analysis_rhexis.json"))
            if "phase_phaco" in user_message:
                return _chat_json(_load("phase_analysis_phaco.json"))
            if "phase_ia" in user_message:
                return _chat_json(_load("phase_analysis_ia.json"))
            raise RuntimeError("unknown phase in user_message")

        if "surgical annotation data normalizer" in system_prompt:
            return _chat_json(_load("data_extractor_ok.json"))

        raise RuntimeError(f"unexpected LLM call: {system_prompt[:80]}")

    llm.chat.side_effect = chat
    llm.model = "gemini-2.5-flash"
    llm._phase_calls = phase_calls
    llm._composer_calls = composer_calls
    return llm


@pytest.mark.asyncio
async def test_orchestrator_full_pipeline():
    s1 = json.loads(_S1.read_text(encoding="utf-8"))
    llm = _make_llm(review_approved=True)
    orch = PipelineOrchestrator(config=_cfg(), llm_client=llm)
    result = await orch.run(
        phases=s1["phases"],
        metrics=s1["metrics"],
        scores=s1["scores"],
        markers=s1["markers"],
        settings={"tone": 2, "emphasis": ["technical"], "ai_config": {"enable_review": True}},
    )
    assert result["metadata"]["fallback_used"] is False
    assert "# Surgical Procedure Evaluation Report" in result["content"]
    assert "quality_reviewer" in " ".join(result["metadata"]["agents_used"])


@pytest.mark.asyncio
async def test_orchestrator_parallel_three_phases():
    s1 = json.loads(_S1.read_text(encoding="utf-8"))
    llm = _make_llm()
    orch = PipelineOrchestrator(config=_cfg(), llm_client=llm)
    await orch.run(
        phases=s1["phases"],
        metrics=s1["metrics"],
        scores=s1["scores"],
        markers=s1["markers"],
        settings={"tone": 2, "ai_config": {"enable_review": False}},
    )
    assert llm._phase_calls["n"] == 3


@pytest.mark.asyncio
async def test_orchestrator_partial_phase_fail_continues():
    s1 = json.loads(_S1.read_text(encoding="utf-8"))
    llm = _make_llm(fail_phase="phase_phaco")
    orch = PipelineOrchestrator(config=_cfg(), llm_client=llm)
    result = await orch.run(
        phases=s1["phases"],
        metrics=s1["metrics"],
        scores=s1["scores"],
        markers=s1["markers"],
        settings={"tone": 2, "ai_config": {"enable_review": False}},
    )
    assert result["metadata"]["fallback_used"] is False
    assert result["content"]


@pytest.mark.asyncio
async def test_orchestrator_fallback_when_no_valid_phases():
    llm = MagicMock()
    orch = PipelineOrchestrator(config=_cfg(), llm_client=llm)
    result = await orch.run(
        phases=[],
        metrics={},
        scores={},
        markers=[],
        settings={"tone": 2},
    )
    assert result["metadata"]["fallback_used"] is True
    assert "Report generation failed" in result["content"] or "annotation_data" in result["content"]


@pytest.mark.asyncio
async def test_orchestrator_fallback_on_llm_failure():
    s1 = json.loads(_S1.read_text(encoding="utf-8"))
    llm = MagicMock()
    llm.chat.side_effect = RuntimeError("LLM down")
    llm.model = "gemini-2.5-flash"
    orch = PipelineOrchestrator(config=_cfg(), llm_client=llm)
    result = await orch.run(
        phases=s1["phases"],
        metrics=s1["metrics"],
        scores=s1["scores"],
        markers=s1["markers"],
        settings={"tone": 2, "ai_config": {"enable_review": False}},
    )
    assert result["metadata"]["fallback_used"] is True
    assert "rule_based_fallback" in result["metadata"]["agents_used"]
    assert "# Surgical Procedure Evaluation Report" in result["content"]


@pytest.mark.asyncio
async def test_orchestrator_review_retry_calls_composer_twice():
    s1 = json.loads(_S1.read_text(encoding="utf-8"))
    llm = _make_llm(review_approved=False)
    orch = PipelineOrchestrator(config=_cfg(enable_review=True), llm_client=llm)
    await orch.run(
        phases=s1["phases"],
        metrics=s1["metrics"],
        scores=s1["scores"],
        markers=s1["markers"],
        settings={"tone": 2, "ai_config": {"enable_review": True}},
    )
    assert llm._composer_calls["n"] == 2


@pytest.mark.asyncio
async def test_orchestrator_cache_hits_on_repeat_phase_calls():
    s1 = json.loads(_S1.read_text(encoding="utf-8"))
    llm = _make_llm()
    cfg = _cfg(enable_cache=True)
    orch = PipelineOrchestrator(config=cfg, llm_client=llm)

    settings = {"tone": 2, "ai_config": {"enable_review": False, "enable_cache": True}}
    first = await orch.run(
        phases=s1["phases"],
        metrics=s1["metrics"],
        scores=s1["scores"],
        markers=s1["markers"],
        settings=settings,
    )
    calls_after_first = llm._phase_calls["n"]
    second = await orch.run(
        phases=s1["phases"],
        metrics=s1["metrics"],
        scores=s1["scores"],
        markers=s1["markers"],
        settings=settings,
    )
    assert second["metadata"]["cache_hits"] >= 1
    assert llm._phase_calls["n"] == calls_after_first
    assert first["metadata"]["cache_hits"] == 0


@pytest.mark.asyncio
async def test_orchestrator_sequential_phases_when_not_parallel():
    s1 = json.loads(_S1.read_text(encoding="utf-8"))
    llm = _make_llm()
    orch = PipelineOrchestrator(config=_cfg(), llm_client=llm)
    await orch.run(
        phases=s1["phases"],
        metrics=s1["metrics"],
        scores=s1["scores"],
        markers=s1["markers"],
        settings={"tone": 2, "ai_config": {"enable_review": False, "parallel_phases": False}},
    )
    assert llm._phase_calls["n"] == 3
