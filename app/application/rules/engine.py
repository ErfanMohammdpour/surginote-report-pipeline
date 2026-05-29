"""YAML-driven rule engine for contradiction / QA detection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.config import RULES_PATH, settings


@dataclass(frozen=True)
class RuleHit:
    rule_id: str
    severity: str
    message: str
    evidence: dict[str, Any]
    linkage: str | None = None


def load_rules_config(path: Path | None = None, overrides: list[dict] | None = None) -> dict:
    p = path or RULES_PATH
    base: dict = {"version": "1.0", "rules": []}
    if p.exists():
        base = yaml.safe_load(p.read_text(encoding="utf-8")) or base
    if overrides:
        by_id = {r["id"]: r for r in base.get("rules", []) if r.get("id")}
        for ov in overrides:
            rid = ov.get("id")
            if rid and rid in by_id:
                by_id[rid] = {**by_id[rid], **ov}
            elif rid:
                by_id[rid] = ov
        base["rules"] = list(by_id.values())
    return base


def _score_ratio(score: float, max_score: float) -> float:
    return score / max_score if max_score else 0.0


def _markers_in_phase(comments: list[dict], phase: dict) -> list[dict]:
    st, et = phase.get("start_time"), phase.get("end_time")
    out = []
    for c in comments:
        ts = c.get("timestamp")
        if ts is None or st is None or et is None:
            continue
        if float(st) <= float(ts) <= float(et):
            out.append(c)
    return out


def _negative_in_phase(comments: list[dict], phase: dict) -> list[dict]:
    return [c for c in _markers_in_phase(comments, phase) if c.get("sentiment") == "negative"]


_SEVERITY_RANK = {"info": 0, "low": 1, "warning": 2, "medium": 3, "error": 4, "critical": 5}


def _apply_threshold_overrides(cfg: dict, hits: list[RuleHit]) -> list[RuleHit]:
    ot = cfg.get("override_thresholds") or {}
    min_sev = ot.get("contradiction_severity_min")
    if min_sev:
        floor = _SEVERITY_RANK.get(str(min_sev).lower(), 0)
        hits = [h for h in hits if _SEVERITY_RANK.get(str(h.severity).lower(), 0) >= floor]
    return hits


def _score_ratio_threshold(cfg: dict, rule_cond: dict) -> float:
    ot = cfg.get("override_thresholds") or {}
    if "score_ratio_gte" in ot:
        return float(ot["score_ratio_gte"])
    return float((rule_cond.get("score_ratio") or {}).get("gte", settings.contradiction_score_ratio_threshold))


def evaluate_rules(
    canonical: dict[str, Any],
    *,
    config: dict | None = None,
    locale: str = "en",
) -> list[RuleHit]:
    cfg = config or load_rules_config()
    rules = [r for r in cfg.get("rules", []) if r.get("enabled", True)]
    phases = canonical.get("phases") or []
    skills = canonical.get("skills") or []
    comments = canonical.get("comments") or []
    hits: list[RuleHit] = []

    phases_by_name = {p["name"]: p for p in phases if p.get("name")}

    for rule in rules:
        rid = rule.get("id", "unknown")
        cond = rule.get("condition") or {}
        sev = rule.get("severity", "info")
        tmpl = rule.get("message_template", rid)

        if rid == "high_score_negative_comment":
            ratio_gte = _score_ratio_threshold(cfg, cond)
            policy = cond.get("linkage_preference", settings.flag_policy)
            neg_all = [c for c in comments if c.get("sentiment") == "negative"]

            for sk in skills:
                ratio = _score_ratio(float(sk["score"]), float(sk["max_score"]))
                if ratio < float(ratio_gte):
                    continue
                phase_name = sk.get("phase_name") or ""
                phase = phases_by_name.get(phase_name)
                bound = _negative_in_phase(comments, phase) if phase else []

                if bound and str(policy).startswith("phase_window"):
                    m0 = sorted(bound, key=lambda x: float(x.get("timestamp") or 0))[0]
                    hits.append(
                        _hit(rule, sev, tmpl, sk, m0, phase_name, ratio, "phase_window", locale)
                    )
                    continue

                if "case_wide" in str(policy) and neg_all:
                    m0 = sorted(neg_all, key=lambda x: float(x.get("timestamp") or 0))[0]
                    note = (
                        "هیچ نشانگر منفی در بازه فاز نبود؛ اتصال case-wide."
                        if locale == "fa"
                        else "No negative marker in phase window; case-wide linkage."
                    )
                    hits.append(
                        _hit(rule, "low" if sev == "warning" else sev, tmpl, sk, m0, phase_name, ratio, "case_wide", locale, extra_note=note)
                    )

        elif rid == "low_score_no_comment":
            ratio_lt = (cond.get("score_ratio") or {}).get("lt", 0.5)
            for sk in skills:
                ratio = _score_ratio(float(sk["score"]), float(sk["max_score"]))
                if ratio >= float(ratio_lt):
                    continue
                phase_name = sk.get("phase_name") or ""
                phase = phases_by_name.get(phase_name)
                if phase and _markers_in_phase(comments, phase):
                    continue
                hits.append(
                    RuleHit(
                        rule_id=rid,
                        severity=sev,
                        message=tmpl.format(
                            skill_name=sk.get("name"),
                            phase_name=phase_name,
                            score=sk.get("score"),
                            max_score=sk.get("max_score"),
                        ),
                        evidence={"skill": sk, "phase": phase_name, "ratio": ratio},
                        linkage="phase_window",
                    )
                )

        elif rid == "phase_duration_mismatch":
            dur_lt = (cond.get("phase_duration_seconds") or {}).get("lt", 60)
            cnt_gte = (cond.get("comment_count_in_phase") or {}).get("gte", 5)
            for ph in phases:
                dur = float(ph.get("end_time", 0)) - float(ph.get("start_time", 0))
                if dur >= float(dur_lt):
                    continue
                in_ph = _markers_in_phase(comments, ph)
                if len(in_ph) < int(cnt_gte):
                    continue
                hits.append(
                    RuleHit(
                        rule_id=rid,
                        severity=sev,
                        message=tmpl.format(
                            phase_name=ph.get("name"),
                            duration_seconds=int(dur),
                            comment_count=len(in_ph),
                        ),
                        evidence={"phase": ph, "duration_seconds": dur, "comment_count": len(in_ph)},
                    )
                )

        elif rid == "comment_cluster_burst":
            cluster = cond.get("comment_cluster") or {}
            window = float(cluster.get("window_seconds", 30))
            min_count = int(cluster.get("min_count", 4))
            timed = sorted(
                [c for c in comments if c.get("timestamp") is not None],
                key=lambda x: float(x["timestamp"]),
            )
            i = 0
            while i < len(timed):
                j = i
                while j < len(timed) and float(timed[j]["timestamp"]) - float(timed[i]["timestamp"]) <= window:
                    j += 1
                count = j - i
                if count >= min_count:
                    hits.append(
                        RuleHit(
                            rule_id=rid,
                            severity=sev,
                            message=tmpl.format(
                                comment_count=count,
                                window_seconds=int(window),
                                cluster_start_display=timed[i].get("video_time_display") or timed[i]["timestamp"],
                            ),
                            evidence={
                                "window_seconds": window,
                                "comment_count": count,
                                "start_timestamp": timed[i]["timestamp"],
                            },
                        )
                    )
                    i = j
                else:
                    i += 1

    return _apply_threshold_overrides(cfg, _dedupe_hits(hits))


def _hit(
    rule: dict,
    sev: str,
    tmpl: str,
    sk: dict,
    marker: dict,
    phase_name: str,
    ratio: float,
    linkage: str,
    locale: str,
    extra_note: str | None = None,
) -> RuleHit:
    msg = tmpl.format(
        skill_name=sk.get("name"),
        phase_name=phase_name,
        score=sk.get("score"),
        max_score=sk.get("max_score"),
        comment_text=marker.get("text") or "",
        video_time_display=marker.get("video_time_display") or marker.get("timestamp"),
    )
    ev = {
        "skill": sk,
        "marker": marker,
        "ratio": round(ratio, 4),
        "linkage": linkage,
        "human_review_required": True,
    }
    if extra_note:
        ev["notes"] = extra_note
    return RuleHit(rule_id=rule.get("id", "high_score_negative_comment"), severity=sev, message=msg, evidence=ev, linkage=linkage)


def _dedupe_hits(hits: list[RuleHit]) -> list[RuleHit]:
    seen: set[tuple] = set()
    out: list[RuleHit] = []
    for h in hits:
        sk = (h.evidence.get("skill") or {}).get("name")
        link = h.linkage or ""
        ts = (h.evidence.get("marker") or {}).get("timestamp")
        key = (h.rule_id, sk, link, ts)
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out


def hits_to_legacy_flags(hits: list[RuleHit], locale: str = "en") -> list[dict]:
    """Map rule hits → legacy report `contradictions.flags` shape."""
    out = []
    for h in hits:
        sk = h.evidence.get("skill") or {}
        marker = h.evidence.get("marker") or {}
        out.append(
            {
                "code": h.rule_id,
                "severity": h.severity,
                "phase_name": sk.get("phase_name"),
                "skill_name": sk.get("name"),
                "score": sk.get("score"),
                "max_score": sk.get("max_score"),
                "ratio": h.evidence.get("ratio"),
                "marker": {
                    "comment_type": marker.get("type") or marker.get("sentiment"),
                    "timestamp_seconds": marker.get("timestamp"),
                    "video_time_display": marker.get("video_time_display"),
                    "title": marker.get("title"),
                    "text": marker.get("text"),
                    **({"notes": h.evidence["notes"]} if h.evidence.get("notes") else {}),
                },
                "linkage": h.linkage,
                "human_review_required": h.evidence.get("human_review_required", True),
                "message": h.message,
            }
        )
    return out
