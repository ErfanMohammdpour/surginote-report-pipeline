"""Multi-format ingest: xlsx, json, csv → legacy ParsedExport-like dict bundle."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

import pandas as pd

from app.domain.canonical import comment_sentiment, parsed_export_to_canonical
from app.domain.errors import ParseError, UploadError
from app.infrastructure.excel.parser import ParsedExport, parse_surginote_xlsx


def detect_format(filename: str, content_type: str | None) -> str:
    name = (filename or "").lower()
    if name.endswith((".xlsx", ".xlsm")):
        return "xlsx"
    if name.endswith(".json"):
        return "json"
    if name.endswith(".csv"):
        return "csv"
    if content_type:
        if "spreadsheet" in content_type or "excel" in content_type:
            return "xlsx"
        if "json" in content_type:
            return "json"
        if "csv" in content_type:
            return "csv"
    raise UploadError("unsupported_format", "Supported: .xlsx, .xlsm, .json, .csv")


def parse_upload(*, filename: str, payload: bytes, content_type: str | None = None) -> tuple[ParsedExport, dict[str, Any], str]:
    fmt = detect_format(filename, content_type)
    if fmt == "xlsx":
        parsed = parse_surginote_xlsx(payload)
        canonical = parsed_export_to_canonical(
            video_info=parsed.video_info,
            phases=parsed.phases,
            skills=parsed.skill_rows,
            comments=parsed.comments,
            raw_payload=parsed.raw_payload,
        )
        return parsed, canonical, fmt

    if fmt == "json":
        return _parse_json(payload)

    if fmt == "csv":
        return _parse_csv(payload, filename)

    raise UploadError("unsupported_format", f"Cannot parse {filename!r}")


def _parse_json(payload: bytes) -> tuple[ParsedExport, dict[str, Any], str]:
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ParseError(f"invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ParseError("JSON root must be object")
    canonical = _normalize_canonical_input(data)
    parsed = _canonical_to_parsed_export(canonical)
    return parsed, canonical, "json"


def _parse_csv(payload: bytes, filename: str) -> tuple[ParsedExport, dict[str, Any], str]:
    text = payload.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise ParseError("CSV empty")

    # Heuristic: skills export
    if "skill_name" in rows[0] or "Skill/Metric Name" in rows[0]:
        canonical = _csv_skills_bundle(rows, filename)
    else:
        raise ParseError("CSV must include skill_name, phase_name, score, max_score columns")

    parsed = _canonical_to_parsed_export(canonical)
    return parsed, canonical, "csv"


def _csv_skills_bundle(rows: list[dict[str, str]], filename: str) -> dict[str, Any]:
    skills = []
    phases_seen: dict[str, dict] = {}
    for r in rows:
        phase = (r.get("phase_name") or r.get("Phase Name") or "").strip()
        skill = (r.get("skill_name") or r.get("Skill/Metric Name") or "").strip()
        if not skill:
            continue
        sc_raw = r.get("score") or r.get("Score")
        mx_raw = r.get("max_score") or r.get("Max Score")
        try:
            sc = float(sc_raw) if sc_raw not in (None, "") else None
            mx = float(mx_raw) if mx_raw not in (None, "") else None
        except ValueError as e:
            raise ParseError(f"invalid numeric score in CSV row: {e}") from e
        if sc is None or mx is None:
            continue
        skills.append({"name": skill, "phase_name": phase or "General", "score": sc, "max_score": mx})
        if phase and phase not in phases_seen:
            phases_seen[phase] = {"name": phase, "start_time": 0.0, "end_time": 3600.0}

    return {
        "video_info": {"name": Path(filename).stem, "video_id": None, "duration_seconds": None, "export_version": "csv"},
        "phases": list(phases_seen.values()) or [{"name": "General", "start_time": 0.0, "end_time": 3600.0}],
        "skills": skills,
        "comments": [],
        "raw_payload": None,
    }


def _normalize_canonical_input(data: dict[str, Any]) -> dict[str, Any]:
    """Accept canonical or legacy-ish JSON."""
    if "video_info" in data and "phases" in data:
        return data
    # legacy flat export
    return {
        "video_info": {"name": data.get("video_name") or data.get("name") or "imported"},
        "phases": data.get("phases") or [],
        "skills": data.get("skills") or [],
        "comments": data.get("comments") or [],
        "raw_payload": data.get("raw_payload"),
    }


def _canonical_to_parsed_export(canonical: dict[str, Any]) -> ParsedExport:
    vi = canonical["video_info"]
    video_info = {
        "Video Name": vi.get("name"),
        "Video ID": vi.get("video_id"),
        "Duration (seconds)": vi.get("duration_seconds"),
        "Export Version": vi.get("export_version"),
    }
    phases = []
    for p in canonical.get("phases") or []:
        phases.append(
            {
                "phase_name": p["name"],
                "short_name": None,
                "start_time_display": None,
                "end_time_display": None,
                "duration_display": None,
                "start_seconds": p.get("start_time"),
                "end_seconds": p.get("end_time"),
                "start_frame": None,
                "end_frame": None,
                "description": p.get("description"),
                "is_custom": None,
                "phaco_method": p.get("phaco_method"),
            }
        )
    skills = [
        {
            "phase_name": s["phase_name"],
            "skill_name": s["name"],
            "score": s["score"],
            "max_score": s["max_score"],
        }
        for s in canonical.get("skills") or []
    ]
    comments = []
    for i, c in enumerate(canonical.get("comments") or [], start=1):
        ctype = c.get("type") or c.get("sentiment") or "unknown"
        comments.append(
            {
                "sort_index": i,
                "video_time_display": c.get("video_time_display"),
                "timestamp_seconds": c.get("timestamp"),
                "comment_type": ctype if ctype != "negative" else "negative",
                "title": c.get("title"),
                "text": c.get("text"),
                "audio_url": None,
            }
        )
        # ensure sentiment mapping path uses comment_type
        if c.get("sentiment") == "negative":
            comments[-1]["comment_type"] = "negative"

    return ParsedExport(
        video_info=video_info,
        phases=phases,
        skill_rows=skills,
        comments=comments,
        raw_payload=canonical.get("raw_payload"),
        warnings=[],
    )
