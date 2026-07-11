from __future__ import annotations

import json
from pathlib import Path

from app.application.ai_pipeline.config import load_ai_pipeline_config
from app.application.ai_pipeline.fallback.report_service import generate_clinical_report
from app.infrastructure.llm.types import LLMProvider

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def test_load_ai_pipeline_config_defaults():
    cfg = load_ai_pipeline_config()
    assert cfg.provider is LLMProvider.GEMINI
    assert cfg.max_retries >= 1


def test_fallback_report_s1_structure():
    data = json.loads((_FIXTURES / "annotation_data_full_s1.json").read_text(encoding="utf-8"))
    md = generate_clinical_report(
        phases=data["phases"],
        metrics=data["metrics"],
        scores=data["scores"],
        settings={"tone": 2, "emphasis": ["technical", "safety"]},
    )
    assert "# Surgical Procedure Evaluation Report" in md
    assert "## Executive Summary" in md
    assert "### Rhexis" in md
    assert "### Phacoemulsification" in md
    assert "### I&A" in md
    assert "## Overall Assessment" in md
    assert "## Recommendations" in md
    assert "SurgiNote AI Clinical Report Service" in md


def test_fallback_report_s2_minimal():
    data = json.loads((_FIXTURES / "annotation_data_minimal.json").read_text(encoding="utf-8"))
    md = generate_clinical_report(
        phases=data["phases"],
        metrics=data["metrics"],
        scores=data["scores"],
        settings={"tone": 4, "emphasis": ["technical"]},
    )
    assert "# Surgical Procedure Evaluation Report" in md
    assert "### Rhexis" in md
    assert "Very Encouraging" in md


def test_fallback_report_requires_recorded_phases():
    try:
        generate_clinical_report(
            phases=[{"id": "p1", "name": "X"}],
            metrics={},
            scores={},
            settings={"tone": 2},
        )
        raised = False
    except ValueError as exc:
        raised = True
        assert "No recorded phases" in str(exc)
    assert raised
