from __future__ import annotations

from app.application.rules.engine import evaluate_rules


def _fixture_canonical():
    return {
        "video_info": {"name": "t"},
        "phases": [{"name": "Alpha", "start_time": 0.0, "end_time": 120.0}],
        "skills": [{"name": "Skill A", "phase_name": "Alpha", "score": 5.0, "max_score": 5.0}],
        "comments": [
            {
                "timestamp": 30.0,
                "text": "oops",
                "sentiment": "negative",
                "video_time_display": "00:30",
                "type": "negative",
            }
        ],
    }


def test_high_score_negative_in_phase_window():
    hits = evaluate_rules(_fixture_canonical(), locale="en")
    assert any(h.rule_id == "high_score_negative_comment" and h.linkage == "phase_window" for h in hits)


def test_low_score_no_comment_rule():
    data = _fixture_canonical()
    data["skills"] = [{"name": "Bad", "phase_name": "Alpha", "score": 1.0, "max_score": 5.0}]
    data["comments"] = []
    hits = evaluate_rules(data)
    assert any(h.rule_id == "low_score_no_comment" for h in hits)
