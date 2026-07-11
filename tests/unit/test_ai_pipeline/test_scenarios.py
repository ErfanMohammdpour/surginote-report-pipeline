"""PDF §9 mandatory scenarios — orchestrator level (mocked LLM, no live API)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.application.ai_pipeline.config import AIPipelineConfig
from app.application.ai_pipeline.fallback.report_service import generate_clinical_report
from app.application.ai_pipeline.orchestrator import PipelineOrchestrator
from app.infrastructure.llm.types import LLMProvider
from tests.unit.test_ai_pipeline.conftest import make_scenario_llm

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


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


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_scenario_s1_full_data_tone_2():
    data = _load_fixture("annotation_data_full_s1.json")
    llm = make_scenario_llm(review_approved=True)
    orch = PipelineOrchestrator(config=_cfg(), llm_client=llm)
    result = await orch.run(
        phases=data["phases"],
        metrics=data["metrics"],
        scores=data["scores"],
        markers=data["markers"],
        settings={"tone": 2, "emphasis": ["technical"], "ai_config": {"enable_review": True}},
    )
    md = result["content"]
    meta = result["metadata"]
    assert meta["fallback_used"] is False
    assert meta["pipeline"] == "ai-agent-v2"
    assert meta["confidence_score"] > 0
    assert "# Surgical Procedure Evaluation Report" in md
    assert "## Executive Summary" in md
    assert "## Overall Assessment" in md
    assert "## Recommendations" in md
    assert md.count("###") >= 3


@pytest.mark.asyncio
async def test_scenario_s2_minimal_tone_4():
    data = _load_fixture("annotation_data_minimal.json")
    llm = make_scenario_llm(review_approved=False)
    orch = PipelineOrchestrator(config=_cfg(enable_review=False), llm_client=llm)
    result = await orch.run(
        phases=data["phases"],
        metrics=data["metrics"],
        scores=data["scores"],
        markers=data["markers"],
        settings={"tone": 4, "ai_config": {"enable_review": False}},
    )
    assert result["metadata"]["fallback_used"] is False
    assert "### Rhexis" in result["content"] or "Rhexis" in result["content"]


@pytest.mark.asyncio
async def test_scenario_s3_fallback_llm_unavailable():
    data = _load_fixture("annotation_data_full_s1.json")
    llm = MagicMock()
    llm.chat.side_effect = RuntimeError("LLM down")
    llm.model = "gemini-2.5-flash"
    orch = PipelineOrchestrator(config=_cfg(), llm_client=llm)
    result = await orch.run(
        phases=data["phases"],
        metrics=data["metrics"],
        scores=data["scores"],
        markers=data["markers"],
        settings={"tone": 2, "ai_config": {"enable_review": False}},
    )
    assert result["metadata"]["fallback_used"] is True
    expected = generate_clinical_report(
        data["phases"], data["metrics"], data["scores"], {"tone": 2}
    )
    assert result["content"] == expected


@pytest.mark.asyncio
async def test_scenario_s4_tone_extremes_same_structure_different_narrative():
    data = _load_fixture("annotation_data_full_s1.json")
    llm = make_scenario_llm(review_approved=True)

    async def run_tone(tone: int) -> str:
        orch = PipelineOrchestrator(config=_cfg(), llm_client=make_scenario_llm())
        result = await orch.run(
            phases=data["phases"],
            metrics=data["metrics"],
            scores=data["scores"],
            markers=data["markers"],
            settings={"tone": tone, "ai_config": {"enable_review": False}},
        )
        return result["content"]

    tone0 = await run_tone(0)
    tone4 = await run_tone(4)
    for marker in (
        "# Surgical Procedure Evaluation Report",
        "## Executive Summary",
        "## Overall Assessment",
        "## Recommendations",
    ):
        assert marker in tone0
        assert marker in tone4

    rule0 = generate_clinical_report(
        data["phases"], data["metrics"], data["scores"], {"tone": 0}
    )
    rule4 = generate_clinical_report(
        data["phases"], data["metrics"], data["scores"], {"tone": 4}
    )
    assert rule0 != rule4
