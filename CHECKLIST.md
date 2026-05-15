# Delivery checklist — Report module + ingest

Use this as acceptance tracking. Tick items when verified.

---

## Phase 0 — Architecture

| # | Item | Done |
|---|------|------|
| 0.1 | Clear MVP vs future (no agent in MVP) | ☐ |
| 0.2 | Layering: domain / application / infrastructure / API | ☐ |
| 0.3 | Pydantic request/response models for HTTP | ☐ |
| 0.4 | Settings via `SN_*` + `GEMINI_*` (see `.env.example`) | ☐ |

---

## Phase 1 — Persistence

| # | Item | Done |
|---|------|------|
| 1.1 | `cases.raw_payload` stores full technical JSON | ☐ |
| 1.2 | Normalized tables + FK cascade | ☐ |
| 1.3 | `case_reports` stores latest generated JSON when `persist=true` | ☐ |

---

## Phase 2 — Excel ingest

| # | Item | Done |
|---|------|------|
| 2.1 | All five canonical sheets parsed | ☐ |
| 2.2 | Aggregate skill rows skipped | ☐ |
| 2.3 | Enrich phase seconds / frames from raw JSON when sheet incomplete | ☐ |
| 2.4 | Enrich comment `timestamp_seconds` from raw markers when needed | ☐ |

---

## Phase 3 — Analytics & flags

| # | Item | Done |
|---|------|------|
| 3.1 | Per-(phase, skill) means with `sample_count` | ☐ |
| 3.2 | Contradiction flags (high ratio + negative marker) | ☐ |
| 3.3 | Policy `phase_window_then_case_wide` configurable | ☐ |
| 3.4 | Pytest covers synthetic overlap scenario | ☐ |

---

## Phase 4 — Report JSON

| # | Item | Done |
|---|------|------|
| 4.1 | `phase_summary` with preserved times/frames | ☐ |
| 4.2 | `score_analysis` + `score_narrative` (English template) | ☐ |
| 4.3 | `comments_timeline` sorted, timestamps preserved | ☐ |
| 4.4 | `contradictions.flags` wired from analytics | ☐ |
| 4.5 | `meta.schema_version` bumped on breaking JSON changes | ☐ |

---

## Phase 5 — API & ops

| # | Item | Done |
|---|------|------|
| 5.1 | `POST /v1/imports` | ☐ |
| 5.2 | `GET /v1/cases/{id}` | ☐ |
| 5.3 | `POST /v1/cases/{id}/reports/generate` | ☐ |
| 5.4 | `GET /v1/cases/{id}/reports/latest` | ☐ |
| 5.5 | `POST /v1/narratives/generate` + case-scoped variant | ☐ |
| 5.6 | `GET /healthz` | ☐ |

---

## Phase 6 — Quality

| # | Item | Done |
|---|------|------|
| 6.1 | `requirements.txt` installs cleanly | ☐ |
| 6.2 | `pytest tests -q` green | ☐ |
| 6.3 | Example LLM prompt doc in `docs/prompts/` | ☐ |
| 6.4 | `.gitignore` covers `data/*.db`, `tests/_pytest.sqlite` | ☐ |

---

*Checklist version `2.0` (English).*
