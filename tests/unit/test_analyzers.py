from __future__ import annotations

from app.application.analyzers import ContradictionAnalyzer, ScoreAnalyzer, TimelineAnalyzer

CANON = {
    "video_info": {"name": "x"},
    "phases": [{"name": "P1", "start_time": 0, "end_time": 60}],
    "skills": [
        {"name": "S1", "phase_name": "P1", "score": 4.0, "max_score": 5.0},
        {"name": "S1", "phase_name": "P1", "score": 5.0, "max_score": 5.0},
    ],
    "comments": [{"timestamp": 10, "text": "ok", "sentiment": "positive"}],
}


def test_score_analyzer_provenance():
    res = ScoreAnalyzer().analyze(CANON)
    assert res.data["S1"]["mean"] == 4.5
    assert res.provenance.calculation_method == "arithmetic_mean"
    assert len(res.provenance.input_values) == 2


def test_timeline_density():
    res = TimelineAnalyzer().analyze(CANON)
    assert res.data["total_comments"] == 1
    assert "P1" in res.data["phase_density_comments_per_minute"]


def test_contradiction_analyzer_flags():
    canon = {
        "video_info": {"name": "x"},
        "phases": [{"name": "P1", "start_time": 0, "end_time": 60}],
        "skills": [{"name": "S1", "phase_name": "P1", "score": 5.0, "max_score": 5.0}],
        "comments": [{"timestamp": 5, "text": "bad", "sentiment": "negative"}],
    }
    res = ContradictionAnalyzer(locale="en").analyze(canon)
    assert res.data["count"] >= 1
    assert res.data["flags"][0]["rule_id"] == "high_score_negative_comment"
