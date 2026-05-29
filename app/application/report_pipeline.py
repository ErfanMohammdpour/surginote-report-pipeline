"""Multi-stage, template-first JSON report."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from app.application.analytics import FlagRecord
from app.application.rules.engine import evaluate_rules, hits_to_legacy_flags, load_rules_config
from app.domain.canonical import parsed_export_to_canonical
from app.config import settings
from app.infrastructure.database import models


REPORT_SCHEMA_VERSION = "1.3.0"


def _skills_means(case: models.CaseORM) -> list[dict]:
    buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
    max_by_key: dict[tuple[str, str], float] = {}
    for s in case.skills:
        key = (s.phase_name, s.skill_name)
        buckets[key].append(float(s.score))
        max_by_key[key] = float(s.max_score)
    out = []
    for (phase_name, skill_name), scores in sorted(buckets.items(), key=lambda x: (x[0][0], x[0][1])):
        out.append(
            {
                "phase": phase_name,
                "skill": skill_name,
                "mean_score": round(sum(scores) / len(scores), 3),
                "max_score": max_by_key[(phase_name, skill_name)],
                "sample_count": len(scores),
            }
        )
    return out


def _overall(skills_mean: list[dict]) -> dict | None:
    if not skills_mean:
        return None
    msum = sum(s["mean_score"] for s in skills_mean)
    mx_max = max(s["max_score"] for s in skills_mean)
    return {"average_score": round(msum / len(skills_mean), 3), "reference_max_score": mx_max}


def _phase_performance_lines(case: models.CaseORM, skills_mean: list[dict], locale: str) -> list[str]:
    by_phase: dict[str, list[dict]] = defaultdict(list)
    for row in skills_mean:
        by_phase[row["phase"]].append(row)
    lines = []
    for ph in sorted(by_phase.keys(), key=lambda z: z):
        rows = by_phase[ph]
        avg = round(sum(r["mean_score"] for r in rows) / len(rows), 2)
        mx = rows[0]["max_score"]
        if locale == "fa":
            lines.append(f"در فاز «{ph}»، میانگین امتیاز مهارت‌ها حدود {avg} از {mx} است.")
        else:
            lines.append(f"In phase «{ph}», mean skill score is about {avg} out of {mx}.")
    ov = _overall(skills_mean)
    if ov:
        if locale == "fa":
            lines.append(
                f"میانگین کل میانگین‌های هر مهارت حدود {ov['average_score']} از {ov['reference_max_score']} است."
            )
        else:
            lines.append(
                f"Overall mean of per-skill means is about {ov['average_score']} out of {ov['reference_max_score']}."
            )
    return lines


def _comment_items(case: models.CaseORM) -> list[dict]:
    sorted_cm = sorted(
        case.comments,
        key=lambda c: (
            float(c.timestamp_seconds) if c.timestamp_seconds is not None else 1e12,
            c.sort_index or 0,
        ),
    )
    out = []
    for i, cm in enumerate(sorted_cm, start=1):
        out.append(
            {
                "order": i,
                "video_time_display": cm.video_time_display,
                "timestamp_seconds": cm.timestamp_seconds,
                "type": cm.comment_type,
                "title": cm.title,
                "text": cm.text,
                "audio_url": cm.audio_url,
                "marker_id": cm.marker_id,
            }
        )
    return out


def flags_to_payload(flags: list[FlagRecord]) -> list[dict]:
    return [
        {
            "code": f.code,
            "severity": f.severity,
            "phase_name": f.phase_name,
            "skill_name": f.skill_name,
            "score": f.score,
            "max_score": f.max_score,
            "ratio": round(f.ratio, 4),
            "marker": f.marker_ref,
            "linkage": f.linkage,
            "human_review_required": f.human_review_required,
        }
        for f in flags
    ]


def build_json_report(case: models.CaseORM, locale: str = "en") -> dict:
    skills_mean = _skills_means(case)
    overall = _overall(skills_mean)

    phases_plain = [
        {
            "phase_name": p.phase_name,
            "phase_id": None,
            "short_name": p.short_name,
            "time_range_display": {"start": p.start_time_display, "end": p.end_time_display},
            "duration_display": p.duration_display,
            "start_seconds": p.start_seconds,
            "end_seconds": p.end_seconds,
            "start_frame": p.start_frame,
            "end_frame": p.end_frame,
            "description": p.description,
            "is_custom": p.is_custom,
            "phaco_method": p.phaco_method,
        }
        for p in case.phases
    ]

    canonical = parsed_export_to_canonical(
        video_info={
            "Video Name": case.video_name,
            "Video ID": case.video_id,
            "Duration (seconds)": case.duration_seconds,
            "Export Version": case.export_version,
        },
        phases=[
            {
                "phase_name": p.phase_name,
                "start_seconds": p.start_seconds,
                "end_seconds": p.end_seconds,
                "description": p.description,
                "phaco_method": p.phaco_method,
            }
            for p in case.phases
        ],
        skills=[
            {"phase_name": s.phase_name, "skill_name": s.skill_name, "score": s.score, "max_score": s.max_score}
            for s in case.skills
        ],
        comments=[
            {
                "comment_type": c.comment_type,
                "timestamp_seconds": c.timestamp_seconds,
                "video_time_display": c.video_time_display,
                "title": c.title,
                "text": c.text,
            }
            for c in case.comments
        ],
        raw_payload=case.raw_payload if isinstance(case.raw_payload, dict) else None,
    )
    cfg = load_rules_config()
    rule_hits = evaluate_rules(canonical, config=cfg, locale=locale)
    flags_payload = hits_to_legacy_flags(rule_hits, locale=locale)

    if locale == "fa":
        limits = [
            "صرفاً بر پایهٔ حاشیه‌نویسی ویدیو؛ معادل گزارش عمل جراحی رسمی نیست.",
            "در صورت تغییر خروجی اکسل یا نسخهٔ ابزار، پارسر را نسخه‌گذاری کنید؛ نسخهٔ export در meta است.",
        ]
    else:
        limits = [
            "Derived from video annotations only; not a formal operative note.",
            "If export columns or tool version change, version the parser; export_version is in meta.",
        ]

    payload = {
        "meta": {
            "schema_version": REPORT_SCHEMA_VERSION,
            "report_locale": locale,
            "export_version": case.export_version,
            "video_id": case.video_id,
            "video_name": case.video_name,
            "duration_seconds": case.duration_seconds,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources": list(case.sources_used or ["xlsx_normalized"]),
            "flag_policy": settings.flag_policy,
            "thresholds": {"score_ratio": settings.contradiction_score_ratio_threshold},
        },
        "sections": {
            "phase_summary": {
                "format": "list",
                "items": phases_plain,
            },
            "score_analysis": {
                "overall": overall,
                "per_skill_means": skills_mean,
                "score_narrative": "\n".join(_phase_performance_lines(case, skills_mean, locale)),
            },
            "comments_timeline": _comment_items(case),
            "contradictions": {"flags": flags_payload},
        },
        "quality": {"limitations": limits},
    }
    return payload
