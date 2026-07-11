"""Integration tests — POST /v1/reports/generate-ai (PDF §9 S1–S4)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.application.ai_pipeline.fallback.report_service import generate_clinical_report
from tests.unit.test_ai_pipeline.conftest import make_scenario_llm

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _load(name: str) -> dict:
    data = json.loads((_FIXTURES / name).read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not str(k).startswith("_")}


def _payload_from_fixture(name: str, *, tone: int = 2, enable_review: bool = False) -> dict:
    body = _load(name)
    body["settings"] = {
        "tone": tone,
        "emphasis": ["technical", "safety"],
        "locale": "en",
        "ai_config": {"enable_review": enable_review, "parallel_phases": True},
    }
    return body


def _patch_llm(monkeypatch, llm: MagicMock) -> None:
    def _factory(**_kwargs):
        return llm

    for target in (
        "app.application.ai_pipeline.service.LLMClient.from_settings",
        "app.application.ai_pipeline.service.LLMClient.from_ai_config",
        "app.application.ai_pipeline.orchestrator.LLMClient.from_settings",
    ):
        monkeypatch.setattr(target, _factory)


@pytest.fixture(autouse=True)
def _reset_llm_cache():
    from app.application.ai_pipeline.cache import reset_llm_cache_for_tests

    reset_llm_cache_for_tests()
    yield
    reset_llm_cache_for_tests()


@pytest.fixture
def mock_ai_llm(monkeypatch):
    llm = make_scenario_llm(review_approved=True)
    _patch_llm(monkeypatch, llm)
    return llm


def _assert_security_headers(response) -> None:
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("x-xss-protection") == "1; mode=block"
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("x-request-id")


def _assert_metadata_shape(metadata: dict, *, expect_ai: bool) -> None:
    assert metadata["pipeline"] == "ai-agent-v2"
    assert "generation_time_seconds" in metadata
    assert "cache_hits" in metadata
    assert "tokens_used" in metadata
    tokens = metadata["tokens_used"]
    assert set(tokens.keys()) >= {"input", "output", "total"}
    if expect_ai:
        assert metadata["agents_used"]
        assert metadata["model"]
        assert metadata["confidence_score"] > 0


@pytest.mark.integration
def test_generate_ai_s1_full(client, mock_ai_llm):
    r = client.post("/v1/reports/generate-ai", json=_payload_from_fixture("annotation_data_full_s1.json", tone=2))
    assert r.status_code == 200
    body = r.json()
    content = body["content"]
    assert body["metadata"]["fallback_used"] is False
    _assert_metadata_shape(body["metadata"], expect_ai=True)
    assert body["generatedAt"].endswith("Z")
    assert "# Surgical Procedure Evaluation Report" in content
    assert "## Executive Summary" in content
    assert "## Recommendations" in content
    assert content.count("### ") >= 3
    _assert_security_headers(r)


@pytest.mark.integration
def test_generate_ai_s2_minimal(client, mock_ai_llm):
    r = client.post(
        "/v1/reports/generate-ai",
        json=_payload_from_fixture("annotation_data_minimal.json", tone=4, enable_review=False),
    )
    assert r.status_code == 200
    body = r.json()
    assert "Rhexis" in body["content"]
    _assert_metadata_shape(body["metadata"], expect_ai=True)


@pytest.mark.integration
def test_generate_ai_s3_fallback(client, monkeypatch):
    llm = MagicMock()
    llm.chat.side_effect = RuntimeError("LLM down")
    llm.model = "gemini-2.5-flash"
    _patch_llm(monkeypatch, llm)

    payload = _payload_from_fixture("annotation_data_full_s1.json", tone=2, enable_review=False)
    r = client.post("/v1/reports/generate-ai", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["metadata"]["fallback_used"] is True
    assert body["metadata"]["fallback_reason"]
    assert body["metadata"]["tokens_used"]["total"] == 0
    expected = generate_clinical_report(
        payload["phases"],
        payload["metrics"],
        payload["scores"],
        {"tone": 2, "emphasis": payload["settings"]["emphasis"]},
    )
    assert body["content"] == expected


@pytest.mark.integration
def test_generate_ai_s4_tone_extremes(client, mock_ai_llm):
    base = _load("annotation_data_full_s1.json")
    base.pop("settings", None)

    def post_tone(tone: int):
        payload = {
            **base,
            "settings": {"tone": tone, "emphasis": ["technical"], "ai_config": {"enable_review": False}},
        }
        return client.post("/v1/reports/generate-ai", json=payload)

    r0 = post_tone(0)
    r4 = post_tone(4)
    assert r0.status_code == 200
    assert r4.status_code == 200
    rule0 = generate_clinical_report(base["phases"], base["metrics"], base["scores"], {"tone": 0})
    rule4 = generate_clinical_report(base["phases"], base["metrics"], base["scores"], {"tone": 4})
    assert rule0 != rule4


@pytest.mark.integration
def test_generate_ai_validation_empty_phases(client):
    r = client.post("/v1/reports/generate-ai", json={"phases": [], "metrics": {}, "scores": {}, "markers": []})
    assert r.status_code == 422
    assert r.json()["code"] == "request_validation_error"


@pytest.mark.integration
def test_generate_ai_validation_bad_tone(client):
    payload = _payload_from_fixture("annotation_data_minimal.json")
    payload["settings"]["tone"] = 9
    r = client.post("/v1/reports/generate-ai", json=payload)
    assert r.status_code == 422


@pytest.mark.integration
def test_generate_ai_validation_bad_marker_missing_timestamp(client):
    payload = _payload_from_fixture("annotation_data_minimal.json")
    payload["markers"] = [{"id": "m1", "type": "comment"}]
    r = client.post("/v1/reports/generate-ai", json=payload)
    assert r.status_code == 422


@pytest.mark.integration
def test_generate_ai_validation_bad_marker_type(client):
    payload = _payload_from_fixture("annotation_data_minimal.json")
    payload["markers"] = [{"id": "m1", "type": "invalid", "timestamp": 1.0}]
    r = client.post("/v1/reports/generate-ai", json=payload)
    assert r.status_code == 422


@pytest.mark.integration
def test_generate_ai_openapi_registered(client):
    spec = client.get("/openapi.json").json()
    assert "/v1/reports/generate-ai" in spec.get("paths", {})
    post = spec["paths"]["/v1/reports/generate-ai"]["post"]
    assert post["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("AIReportResponse")


@pytest.mark.integration
def test_generate_ai_rate_limiter_registered(client):
    assert getattr(client.app.state, "limiter", None) is not None


@pytest.mark.integration
def test_generate_ai_cache_hits_on_repeat(client, mock_ai_llm):
    payload = _payload_from_fixture("annotation_data_minimal.json", tone=2, enable_review=False)
    payload["settings"]["ai_config"]["enable_cache"] = True
    first = client.post("/v1/reports/generate-ai", json=payload)
    second = client.post("/v1/reports/generate-ai", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["metadata"]["cache_hits"] == 0
    assert second.json()["metadata"]["cache_hits"] >= 1
