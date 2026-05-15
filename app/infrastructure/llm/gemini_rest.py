"""Gemini REST (v1beta) generateContent — no google SDK dependency."""

from __future__ import annotations

from typing import Any

import httpx


class GeminiError(Exception):
    def __init__(self, status_code: int, body: str):
        super().__init__(f"Gemini HTTP {status_code}: {body[:500]}")
        self.status_code = status_code
        self.body = body


def generate_content(
    *,
    api_key: str,
    model: str,
    system_instruction: str,
    user_message: str,
    temperature: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    """
    POST /v1beta/models/{model}:generateContent

    Returns:
        dict with keys: text (str), raw (full JSON), finish_reason (str|None)
    """
    safe_model = model.removeprefix("models/")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{safe_model}:generateContent"
    payload: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": 8192},
    }

    with httpx.Client(timeout=timeout_seconds) as client:
        r = client.post(url, params={"key": api_key}, json=payload)

    if r.status_code >= 400:
        raise GeminiError(r.status_code, r.text)

    data = r.json()
    text = ""
    parts = []
    try:
        cands = data.get("candidates") or []
        if cands:
            content = cands[0].get("content") or {}
            parts = content.get("parts") or []
            text = "".join(p.get("text") or "" for p in parts)
    except Exception:  # noqa: BLE001
        text = ""

    finish_reason = None
    try:
        cands = data.get("candidates") or []
        if cands:
            finish_reason = cands[0].get("finishReason")
    except Exception:  # noqa: BLE001
        finish_reason = None

    return {"text": text.strip(), "raw": data, "finish_reason": finish_reason}
