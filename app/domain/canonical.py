"""Canonical internal format + sentiment helpers."""

from __future__ import annotations

from typing import Any, Literal

Sentiment = Literal["positive", "negative", "neutral", "unknown"]


def comment_sentiment(comment_type: str | None) -> Sentiment:
    t = (comment_type or "").strip().lower()
    if t in {"negative", "warn", "warning", "critical"}:
        return "negative"
    if t in {"positive", "praise", "good"}:
        return "positive"
    if t in {"neutral", "note", "info", "observation"}:
        return "neutral"
    return "unknown"


def parsed_export_to_canonical(
    *,
    video_info: dict[str, Any],
    phases: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    comments: list[dict[str, Any]],
    raw_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map legacy parser output → canonical JSON for schema validation + analyzers."""

    def _vid_name() -> str:
        for k in ("Video Name", "video_name", "name"):
            if k in video_info and video_info[k]:
                return str(video_info[k])
        return "unknown"

    canon_phases = []
    for p in phases:
        st = p.get("start_seconds")
        et = p.get("end_seconds")
        if st is None:
            st = 0.0
        if et is None:
            et = float(st) + 1.0
        canon_phases.append(
            {
                "name": p["phase_name"],
                "start_time": float(st),
                "end_time": float(et),
                "description": p.get("description"),
                "phaco_method": p.get("phaco_method"),
            }
        )

    canon_skills = [
        {
            "name": s["skill_name"],
            "phase_name": s["phase_name"],
            "score": float(s["score"]),
            "max_score": float(s["max_score"]),
        }
        for s in skills
    ]

    canon_comments = []
    for c in comments:
        ctype = str(c.get("comment_type") or "unknown")
        canon_comments.append(
            {
                "timestamp": c.get("timestamp_seconds"),
                "text": c.get("text") or "",
                "sentiment": comment_sentiment(ctype),
                "title": c.get("title"),
                "type": ctype,
                "video_time_display": c.get("video_time_display"),
            }
        )

    return {
        "video_info": {
            "name": _vid_name(),
            "video_id": video_info.get("Video ID"),
            "duration_seconds": video_info.get("Duration (seconds)"),
            "export_version": video_info.get("Export Version"),
        },
        "phases": canon_phases,
        "skills": canon_skills,
        "comments": canon_comments,
        "raw_payload": raw_payload,
    }
