from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from app.domain.errors import ParseError
from app.domain.timecode import mmss_clock_to_seconds, video_clock_to_seconds


def _scalar(v: Any) -> Any:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return v


def _norm_key(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip())


@dataclass
class ParsedExport:
    video_info: dict[str, Any]
    phases: list[dict[str, Any]]
    skill_rows: list[dict[str, Any]]
    comments: list[dict[str, Any]]
    raw_payload: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)


def _safe_json_load(blob: Any) -> dict[str, Any] | None:
    if blob is None or (isinstance(blob, float) and pd.isna(blob)):
        return None
    raw = str(blob).strip()
    if not raw:
        return None
    try:
        out = json.loads(raw)
        return out if isinstance(out, dict) else None
    except json.JSONDecodeError:
        return None


def _read_sheet(path_or_buf: Path | io.BytesIO, name: str) -> pd.DataFrame:
    try:
        return pd.read_excel(path_or_buf, sheet_name=name, header=None)
    except ValueError as e:
        raise ParseError(f"Missing sheet {name!r}: {e}") from e


def parse_surginote_xlsx(source: Path | bytes) -> ParsedExport:
    """Parse canonical SurgiNote multi-sheet Excel export."""

    buf: Path | io.BytesIO = source if isinstance(source, Path) else io.BytesIO(source)
    warnings: list[str] = []

    xl = pd.ExcelFile(buf)

    expected = {"Video Info", "Phases", "Skills & Ratings", "Comments & Notes", "Raw Data (Technical)"}
    missing = expected - set(xl.sheet_names)
    if missing:
        warnings.append(f"Missing optional sheets (may break strict validation): {sorted(missing)}")

    df_info = pd.read_excel(buf, sheet_name="Video Info", header=None)
    video_info: dict[str, Any] = {}
    for _, row in df_info.iterrows():
        k, v = row[0], row[1] if len(row) > 1 else None
        kk = _scalar(k)
        if kk is None or str(kk).strip() == "" or str(kk) == "nan":
            continue
        video_info[_norm_key(str(kk))] = None if pd.isna(v) else _maybe_number(v)

    df_ph = pd.read_excel(buf, sheet_name="Phases", header=0)
    phases: list[dict[str, Any]] = []
    for _, row in df_ph.iterrows():
        name = row.get("Phase Name")
        if pd.isna(name) or str(name).strip().lower().startswith("phase name"):
            continue
        pname = str(name).strip()
        st = mmss_clock_to_seconds(row.get("Start Time"))
        et = mmss_clock_to_seconds(row.get("End Time"))
        phases.append(
            {
                "phase_name": pname,
                "short_name": None if pd.isna(row.get("Short Name")) else str(row.get("Short Name")).strip(),
                "start_time_display": None if pd.isna(row.get("Start Time")) else str(row.get("Start Time")).strip(),
                "end_time_display": None if pd.isna(row.get("End Time")) else str(row.get("End Time")).strip(),
                "duration_display": None if pd.isna(row.get("Duration")) else str(row.get("Duration")).strip(),
                "start_seconds": st,
                "end_seconds": et,
                "start_frame": None if pd.isna(row.get("Start Frame")) else int(row.get("Start Frame")),
                "end_frame": None if pd.isna(row.get("End Frame")) else int(row.get("End Frame")),
                "description": None if pd.isna(row.get("Description")) else str(row.get("Description")).strip(),
                "is_custom": _truthy_custom(row.get("Is Custom")),
                "phaco_method": None if pd.isna(row.get("Phaco Method")) else str(row.get("Phaco Method")).strip(),
            }
        )

    df_sk = pd.read_excel(buf, sheet_name="Skills & Ratings", header=0)
    reserved_phase_tokens = {"", "phase averages", "overall average", "nan"}
    skill_rows: list[dict[str, Any]] = []
    for _, row in df_sk.iterrows():
        p = row.get("Phase Name")
        s = row.get("Skill/Metric Name")
        if pd.isna(p) and pd.isna(s):
            continue
        p_str = "" if pd.isna(p) else str(p).strip()
        s_str = "" if pd.isna(s) else str(s).strip()

        lp = p_str.lower().strip()
        ls = s_str.lower().strip()

        if lp in reserved_phase_tokens and ls == "":
            continue
        if "phase averages" in lp or "overall average" in lp or "all phases combined" in lp:
            continue
        if "average score" in ls or ls.endswith("average score"):
            continue
        if not s_str:
            continue

        score = row.get("Score")
        mx = row.get("Max Score")
        if pd.isna(score) or pd.isna(mx):
            warnings.append(f"Skipped skill row missing score/max: phase={p_str!r} skill={s_str!r}")
            continue
        skill_rows.append(
            {
                "phase_name": p_str,
                "skill_name": s_str,
                "score": float(score),
                "max_score": float(mx),
            }
        )

    df_cm = pd.read_excel(buf, sheet_name="Comments & Notes", header=0)
    comments: list[dict[str, Any]] = []
    idx = 0
    for _, row in df_cm.iterrows():
        # header guard
        t = row.get("Type") or row.get("type")
        if pd.isna(t) and pd.isna(row.get("Full Text/Description")) and pd.isna(row.get("#")):
            continue
        vt = row.get("Video Time")
        if str(vt).strip().startswith("Video Time"):
            continue
        idx += 1
        comments.append(
            {
                "sort_index": idx,
                "video_time_display": None if pd.isna(vt) else str(vt).strip(),
                "timestamp_seconds": video_clock_to_seconds(vt),
                "comment_type": str(t).strip() if not pd.isna(t) else "unknown",
                "title": None if pd.isna(row.get("Title/Label")) else str(row.get("Title/Label")).strip(),
                "text": None if pd.isna(row.get("Full Text/Description")) else str(row.get("Full Text/Description")).strip(),
                "audio_url": None,
            }
        )

    df_raw = pd.read_excel(buf, sheet_name="Raw Data (Technical)", header=None)
    raw_payload: dict[str, Any] | None = None
    if df_raw.shape[0] >= 2 and df_raw.shape[1] >= 4:
        blob = df_raw.iloc[1, 3]
        raw_payload = _safe_json_load(blob)
        if raw_payload is None:
            warnings.append("Raw Data sheet JSON could not be parsed; continuing without raw_payload.")

    if raw_payload is not None:
        _enrich_timestamps_from_raw(comments, raw_payload)

    phases = enrich_phases_from_raw(phases, raw_payload)

    return ParsedExport(
        video_info=video_info,
        phases=phases,
        skill_rows=skill_rows,
        comments=_sort_comments(comments),
        raw_payload=raw_payload,
        warnings=warnings,
    )


def _maybe_number(v: Any) -> Any:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if float(v).is_integer():
            return int(v)
        return float(v)
    return v


def _truthy_custom(v: Any) -> bool | None:
    if pd.isna(v):
        return None
    s = str(v).strip().lower()
    if s in {"yes", "true", "1"}:
        return True
    if s in {"no", "false", "0"}:
        return False
    return None


def _enrich_timestamps_from_raw(comments: list[dict[str, Any]], raw: dict[str, Any]) -> None:
    markers = raw.get("markers") or []
    if not isinstance(markers, list):
        return
    by_title: dict[str, float] = {}
    for m in markers:
        if not isinstance(m, dict):
            continue
        ts = m.get("timestamp")
        if isinstance(ts, (int, float)):
            title = str(m.get("title") or "")
            by_title[title] = float(ts)

    for c in comments:
        if c.get("timestamp_seconds") is None and c.get("title"):
            hit = by_title.get(str(c["title"]))
            if hit is not None:
                c["timestamp_seconds"] = hit


def enrich_phases_from_raw(phases: list[dict[str, Any]], raw: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not raw:
        return phases
    raw_phases = raw.get("phases")
    if not isinstance(raw_phases, list):
        return phases
    by_name = {str(p.get("name")): p for p in raw_phases if isinstance(p, dict) and p.get("name")}

    out: list[dict[str, Any]] = []
    for base in phases:
        cur = dict(base)
        name = cur.get("phase_name")
        rp = by_name.get(str(name)) if name else None
        st = cur.get("start_seconds")
        et = cur.get("end_seconds")
        phase_id = None
        if rp:
            phase_id = rp.get("id")
            if st is None and isinstance(rp.get("startTime"), (int, float)):
                st = float(rp["startTime"])
            if et is None and isinstance(rp.get("endTime"), (int, float)):
                et = float(rp["endTime"])
            sf = rp.get("startFrame")
            ef = rp.get("endFrame")
            if cur.get("start_frame") is None and sf is not None and not pd.isna(sf):
                cur["start_frame"] = int(sf)
            if cur.get("end_frame") is None and ef is not None and not pd.isna(ef):
                cur["end_frame"] = int(ef)
        cur["start_seconds"] = st
        cur["end_seconds"] = et
        cur["phase_id"] = phase_id
        out.append(cur)
    return out


def _sort_comments(comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(c: dict[str, Any]) -> tuple[float, int]:
        ts = c.get("timestamp_seconds")
        if isinstance(ts, (int, float)):
            return float(ts), int(c.get("sort_index") or 0)
        # fallback preserve sheet order but after timed
        return float("inf"), int(c.get("sort_index") or 0)

    return sorted(comments, key=key)
