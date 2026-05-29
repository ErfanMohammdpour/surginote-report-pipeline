"""JSON Schema validation with structured, actionable errors."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

from app.config import CANONICAL_SCHEMA_PATH


def _load_validator() -> Draft202012Validator:
    schema = json.loads(CANONICAL_SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


_VALIDATOR: Draft202012Validator | None = None


def get_validator() -> Draft202012Validator:
    global _VALIDATOR  # noqa: PLW0603
    if _VALIDATOR is None:
        _VALIDATOR = _load_validator()
    return _VALIDATOR


def _code_for(err: jsonschema.ValidationError) -> str:
    msg = (err.message or "").lower()
    if "less than" in msg or "greater than" in msg:
        return "INVALID_TIME_RANGE"
    if "score" in msg and "max" in msg:
        return "SCORE_OUT_OF_RANGE"
    return "SCHEMA_VIOLATION"


def validate_canonical(data: dict[str, Any]) -> dict[str, Any]:
    """Return {valid, errors[]} per canonical validation spec."""
    validator = get_validator()
    errors: list[dict[str, Any]] = []

    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = "$"
        if err.path:
            path += "." + ".".join(str(p) for p in err.path)
        errors.append(
            {
                "path": path,
                "message": err.message,
                "code": _code_for(err),
                "severity": "error",
            }
        )

    # Business rules beyond JSON Schema
    for i, ph in enumerate(data.get("phases") or []):
        if isinstance(ph, dict):
            st, et = ph.get("start_time"), ph.get("end_time")
            if isinstance(st, (int, float)) and isinstance(et, (int, float)) and st >= et:
                errors.append(
                    {
                        "path": f"$.phases[{i}].start_time",
                        "message": "start_time must be less than end_time",
                        "code": "INVALID_TIME_RANGE",
                        "severity": "error",
                    }
                )

    for i, sk in enumerate(data.get("skills") or []):
        if isinstance(sk, dict):
            sc, mx = sk.get("score"), sk.get("max_score")
            if isinstance(sc, (int, float)) and isinstance(mx, (int, float)) and sc > mx:
                errors.append(
                    {
                        "path": f"$.skills[{i}].score",
                        "message": "score exceeds max_score",
                        "code": "SCORE_OUT_OF_RANGE",
                        "severity": "error",
                    }
                )

    return {"valid": len(errors) == 0, "errors": errors}
