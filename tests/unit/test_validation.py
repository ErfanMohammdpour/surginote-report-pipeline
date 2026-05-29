from __future__ import annotations

from app.domain.validation import validate_canonical


def test_invalid_time_range():
    data = {
        "video_info": {"name": "x"},
        "phases": [{"name": "P", "start_time": 100, "end_time": 10}],
        "skills": [{"name": "S", "phase_name": "P", "score": 1, "max_score": 5}],
        "comments": [],
    }
    out = validate_canonical(data)
    assert out["valid"] is False
    assert any(e["code"] == "INVALID_TIME_RANGE" for e in out["errors"])
