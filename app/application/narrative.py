"""Compose prompts and call Gemini from structured report JSON."""

from __future__ import annotations

import json

from app.config import settings
from app.infrastructure.llm.gemini_rest import generate_content


SYSTEM_INSTRUCTION = """You summarize surgical VIDEO ANNOTATION ONLY, strictly from INPUT_JSON.
Hard rules:
- Never invent anatomy, diagnoses, indications, meds, implants, complications, outcomes, identity, or laterality unless explicitly stated in INPUT_JSON strings.
- Do not prescribe treatment beyond generic educational wording; phrase as review / debrief, not formal medical orders.
- Preserve every cited video timestamp or time display verbatim when quoting observations from comments_timeline or phase ranges.
- If JSON lacks clinical metadata, include a concise "Limitations" section stating data are annotation-derived only.

Output format:
Markdown with headings:
1 Case context — only meta + descriptive fields already present (video name, duration, export version if shown).
2 Procedural chronology — from sections.phase_summary (time ranges, phase names, descriptions).
3 Performance — only from sections.score_analysis (numbers, means; no invented benchmarks).
4 Observations — chronological from sections.comments_timeline; quote timestamps.
5 Flags / QA — from sections.contradictions.flags; if empty, state none detected.

Write the Markdown body in the language requested by the user message (e.g. English or another language if explicitly asked in EXTRA_INSTRUCTIONS). Default to clear English clinical debrief prose unless EXTRA_INSTRUCTIONS specify otherwise.
"""


def build_user_message(*, report: dict, locale: str, extra_instructions: str | None) -> str:
    loc = (locale or "en").strip()
    prefix = (
        f"Output locale tag: {loc}. Produce Markdown in English unless EXTRA_INSTRUCTIONS explicitly request another language.\n"
    )
    extra = ""
    if extra_instructions and extra_instructions.strip():
        extra = "\nEXTRA_INSTRUCTIONS_FROM_USER:\n" + extra_instructions.strip() + "\n"
    blob = json.dumps(report, ensure_ascii=False, indent=2)
    return prefix + extra + "\nINPUT_JSON:\n```json\n" + blob + "\n```"


def synthesize_markdown_report(
    *,
    report: dict,
    locale: str = "en",
    extra_instructions: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    timeout_seconds: float | None = None,
) -> dict:
    """Call Gemini and return markdown + diagnostics."""
    key = api_key or settings.gemini_api_key
    if not key or not key.strip():
        raise ValueError("gemini_api_key_missing")

    res = generate_content(
        api_key=key.strip(),
        model=(model or settings.gemini_model).strip(),
        system_instruction=SYSTEM_INSTRUCTION,
        user_message=build_user_message(report=report, locale=locale, extra_instructions=extra_instructions),
        temperature=float(temperature if temperature is not None else settings.gemini_temperature),
        timeout_seconds=float(timeout_seconds if timeout_seconds is not None else settings.gemini_timeout_seconds),
    )
    return {
        "markdown": res["text"],
        "model": (model or settings.gemini_model).strip(),
        "locale": locale,
        "finish_reason": res.get("finish_reason"),
        "provider_raw": res.get("raw"),
    }
