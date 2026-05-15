"""Deterministic contradiction flags derived from timestamps + bounded scores."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FlagRecord:
    code: str
    severity: str
    phase_name: str | None
    skill_name: str | None
    score: float
    max_score: float
    ratio: float
    marker_ref: dict
    linkage: str
    human_review_required: bool


def _is_negative(marker_type: str) -> bool:
    t = (marker_type or "").strip().lower()
    return t in {"negative", "warn", "warning"}


def _marker_in_phase(ts: float | None, p_start: float | None, p_end: float | None) -> bool:
    if ts is None or p_start is None or p_end is None:
        return False
    return p_start <= ts <= p_end


_CASE_WIDE_NOTES = {
    "en": "No negative marker fell inside phase time window — case-wide linkage heuristic. Human review required.",
    "fa": "هیچ نشانگر منفی‌ای در بازهٔ زمانی این فاز نبود؛ اتصال سراسری (case-wide) اعمال شده است. بازبینی انسانی لازم است.",
}


def compute_flags_for_case(
    *,
    phases: list[dict],
    skills: list[dict],
    comments: list[dict],
    score_ratio_threshold: float,
    policy: str,
    report_locale: str = "en",
) -> list[FlagRecord]:
    neg_markers = [c for c in comments if _is_negative(str(c.get("comment_type") or ""))]
    flags: list[FlagRecord] = []

    phases_by_name = {str(p["phase_name"]): p for p in phases if p.get("phase_name")}

    for sk in skills:
        score = float(sk["score"])
        mx = float(sk["max_score"])
        ratio = score / mx if mx else 0.0
        if ratio < score_ratio_threshold:
            continue
        phase_name = str(sk.get("phase_name") or "")

        # markers tied to phase window first
        bound_markers = []
        p = phases_by_name.get(phase_name)
        if p:
            p_start = p.get("start_seconds")
            p_end = p.get("end_seconds")
            for m in neg_markers:
                ts = m.get("timestamp_seconds")
                if isinstance(ts, (int, float)) and _marker_in_phase(float(ts), float(p_start) if p_start is not None else None, float(p_end) if p_end is not None else None):
                    bound_markers.append(m)

        if bound_markers and policy.startswith("phase_window"):
            m0 = sorted(bound_markers, key=lambda x: float(x.get("timestamp_seconds") or 0.0))[0]
            flags.append(
                FlagRecord(
                    code="high_score_with_negative_comment",
                    severity="medium",
                    phase_name=phase_name or None,
                    skill_name=str(sk.get("skill_name")),
                    score=score,
                    max_score=mx,
                    ratio=ratio,
                    marker_ref={
                        "comment_type": m0.get("comment_type"),
                        "timestamp_seconds": m0.get("timestamp_seconds"),
                        "video_time_display": m0.get("video_time_display"),
                        "title": m0.get("title"),
                        "text": m0.get("text"),
                    },
                    linkage="phase_window",
                    human_review_required=True,
                )
            )
            continue

        if policy.endswith("then_case_wide") and neg_markers:
            m0 = sorted(neg_markers, key=lambda x: float(x.get("timestamp_seconds") or 0.0))[0]
            flags.append(
                FlagRecord(
                    code="high_score_with_negative_comment",
                    severity="low",
                    phase_name=phase_name or None,
                    skill_name=str(sk.get("skill_name")),
                    score=score,
                    max_score=mx,
                    ratio=ratio,
                    marker_ref={
                        "comment_type": m0.get("comment_type"),
                        "timestamp_seconds": m0.get("timestamp_seconds"),
                        "video_time_display": m0.get("video_time_display"),
                        "title": m0.get("title"),
                        "text": m0.get("text"),
                        "notes": _CASE_WIDE_NOTES.get(report_locale, _CASE_WIDE_NOTES["en"]),
                    },
                    linkage="case_wide",
                    human_review_required=True,
                )
            )

    # de-dupe (phase/skill/linkage)
    dedup_keys: set[tuple] = set()
    out: list[FlagRecord] = []
    for f in flags:
        k = (f.skill_name or "", f.phase_name or "", f.linkage, f.marker_ref.get("timestamp_seconds"))
        if k in dedup_keys:
            continue
        dedup_keys.add(k)
        out.append(f)
    return out
