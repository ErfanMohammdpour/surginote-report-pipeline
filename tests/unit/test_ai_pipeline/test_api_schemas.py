from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.schemas import GenerateReportRequest, GenerateReportSettings


def test_generate_report_request_requires_phases():
    with pytest.raises(ValidationError):
        GenerateReportRequest(phases=[])


def test_generate_report_settings_tone_bounds():
    with pytest.raises(ValidationError):
        GenerateReportSettings(tone=5)


def test_generate_report_request_accepts_marker():
    req = GenerateReportRequest(
        phases=[{"id": "p1", "name": "Rhexis", "startTime": 0.0, "endTime": 1.0}],
        markers=[{"id": "m1", "type": "comment", "timestamp": 1.0}],
    )
    assert req.markers[0].id == "m1"


def test_generate_report_request_rejects_invalid_marker_type():
    with pytest.raises(ValidationError):
        GenerateReportRequest(
            phases=[{"id": "p1", "name": "Rhexis", "startTime": 0.0, "endTime": 1.0}],
            markers=[{"id": "m1", "type": "bogus", "timestamp": 1.0}],
        )
