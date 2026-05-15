"""Time parsing for SurgiNote Excel columns (human-facing clock strings)."""

from __future__ import annotations


def mmss_clock_to_seconds(s: object) -> float | None:
    if s is None:
        return None
    raw = str(s).strip()
    if not raw or raw.lower() == "nan":
        return None
    parts = raw.replace("\u061b", ":").split(":")
    try:
        if len(parts) == 2:
            m, sec = parts
            return int(m) * 60 + float(sec)
        if len(parts) == 3:
            h, m, sec = parts
            return int(h) * 3600 + int(m) * 60 + float(sec)
    except (ValueError, TypeError):
        return None
    return None


def video_clock_to_seconds(s: object) -> float | None:
    """`Video Time` like `03:02` — interpreted as MM:SS on same convention as spreadsheet."""
    return mmss_clock_to_seconds(s)
