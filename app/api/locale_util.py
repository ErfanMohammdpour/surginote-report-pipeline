"""Report locale `en` | `fa` — coercion for query params vs config."""

from __future__ import annotations

from typing import Literal

from fastapi import HTTPException

ReportLocale = Literal["en", "fa"]


def parse_strict_locale(raw: str | None, *, fallback: ReportLocale | None = None) -> ReportLocale:
    """First segment of BCP47-ish tag: `en`, `en-US`, `fa`, `fa-IR`."""
    if raw is None:
        if fallback is not None:
            return fallback
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_locale", "message": "locale must be 'en' or 'fa'"},
        )
    tok = str(raw).strip().lower().replace("_", "-").split("-")[0]
    if tok == "en":
        return "en"
    if tok == "fa":
        return "fa"
    if fallback is not None and raw == "":
        return fallback
    raise HTTPException(
        status_code=400,
        detail={"code": "invalid_locale", "message": "locale must be 'en' or 'fa'"},
    )


def resolve_report_locale(query_value: str | None, configured_default: str) -> ReportLocale:
    """Query overrides `SN_REPORT_LOCALE` default when query is non-empty."""
    if query_value is not None and str(query_value).strip() != "":
        return parse_strict_locale(query_value, fallback=None)
    return parse_strict_locale(configured_default, fallback="en")
