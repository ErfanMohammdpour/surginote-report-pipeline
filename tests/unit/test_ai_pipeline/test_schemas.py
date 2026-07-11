from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.application.ai_pipeline.schemas import (
    AnnotationPayload,
    ComposerOutput,
    GenerateSettings,
    MarkersAnalysisOutput,
    PhaseAnalysisOutput,
    PhaseInput,
    QualityReviewOutput,
)


def test_annotation_payload_requires_phases():
    with pytest.raises(ValidationError):
        AnnotationPayload(phases=[])


def test_phase_input_minimal():
    p = PhaseInput(id="phase_1", name="Rhexis")
    assert p.id == "phase_1"


def test_generate_settings_tone_bounds():
    with pytest.raises(ValidationError):
        GenerateSettings(tone=5)


def test_phase_analysis_output_confidence_bounds():
    with pytest.raises(ValidationError):
        PhaseAnalysisOutput(
            phase_id="p1",
            clinical_narrative="ok",
            confidence_score=1.5,
        )


def test_markers_analysis_emotion_trend_enum():
    out = MarkersAnalysisOutput(
        emotion_trend="mixed",
        alignment_with_scores="aligned",
        confidence_score=0.8,
    )
    assert out.emotion_trend == "mixed"


def test_composer_output_requires_content():
    out = ComposerOutput(content="# Report", confidence_score=0.9)
    assert out.content.startswith("#")


def test_quality_review_output():
    out = QualityReviewOutput(overall_quality_score=0.95, approved=True)
    assert out.approved is True


def test_annotation_payload_from_s1_shape():
    payload = AnnotationPayload(
        phases=[PhaseInput(id="p1", name="Rhexis", startTime=1.0, endTime=2.0)],
        metrics={"p1": [{"id": "m1", "name": "Skill"}]},
        scores={"p1": {"m1": 4.0}},
    )
    assert payload.phases[0].name == "Rhexis"
