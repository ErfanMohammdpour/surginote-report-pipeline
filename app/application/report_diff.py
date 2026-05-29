"""Deep diff between two report payloads — all sections."""

from __future__ import annotations

from typing import Any


def _get_path(obj: Any, path: str) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _scalar_diff(a: Any, b: Any) -> dict | None:
    if a == b:
        return None
    change = None
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        change = f"{b - a:+.4g}"
    return {"old": a, "new": b, "change": change}


def _list_diff_by_id(a: list, b: list) -> dict | None:
    ids_a = {f.get("id"): f for f in a if isinstance(f, dict) and f.get("id")}
    ids_b = {f.get("id"): f for f in b if isinstance(f, dict) and f.get("id")}
    added = [v for k, v in ids_b.items() if k not in ids_a]
    removed = [v for k, v in ids_a.items() if k not in ids_b]
    if added or removed:
        return {"added": added, "removed": removed}
    return None


def diff_reports(a: dict, b: dict) -> dict:
    """Compare all sections of two schema-2.0 reports."""
    differences: dict[str, Any] = {}

    # Scalar paths to diff across all sections
    scalar_paths = [
        "sections.score_analysis.data.overall_average",
        "sections.phase_summary.data.total_phases",
        "sections.comment_timeline.data.total_comments",
        "sections.contradictions.data.count",
    ]
    for path in scalar_paths:
        d = _scalar_diff(_get_path(a, path), _get_path(b, path))
        if d:
            differences[path] = d

    # List diffs (flags, clusters, etc.)
    list_paths: list[tuple[str, str]] = [
        ("sections.contradictions.data.flags", "id"),
        ("sections.score_analysis.data.outliers", "skill"),
        ("sections.comment_timeline.data.activity_clusters", "start"),
    ]
    for path, _id_key in list_paths:
        la = _get_path(a, path) or []
        lb = _get_path(b, path) or []
        if not isinstance(la, list) or not isinstance(lb, list):
            continue
        d = _list_diff_by_id(la, lb)
        if d:
            differences[path] = d

    # Per-skill score drift
    skills_a = _get_path(a, "sections.score_analysis.data") or {}
    skills_b = _get_path(b, "sections.score_analysis.data") or {}
    skill_diffs: dict[str, Any] = {}
    all_skills = set(skills_a.keys()) | set(skills_b.keys())
    skip = {"overall_average"}
    for sk in all_skills:
        if sk in skip:
            continue
        mean_a = (skills_a.get(sk) or {}).get("mean") if isinstance(skills_a.get(sk), dict) else None
        mean_b = (skills_b.get(sk) or {}).get("mean") if isinstance(skills_b.get(sk), dict) else None
        d = _scalar_diff(mean_a, mean_b)
        if d:
            skill_diffs[sk] = d
    if skill_diffs:
        differences["sections.score_analysis.skill_means"] = skill_diffs

    return {
        "report_1": a.get("report_id"),
        "report_2": b.get("report_id"),
        "schema_version_1": a.get("schema_version"),
        "schema_version_2": b.get("schema_version"),
        "differences": differences,
        "has_changes": bool(differences),
    }
