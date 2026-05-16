# SurgiNote Report Module — Data Ingestion & Structured Report (FastAPI)

This document describes the **implementation contract** for the operational task: **ingest SurgiNote Excel export → persist → multi-stage structured report as JSON**, aligned with prior task materials (Task1 PDF, ARAS technical PDF, Task2 PDF) and the real `case_4693` workbook shape.

---

## 1. Workbook contract (`xlsx`)

1. **Video Info** — `Property | Value` rows (`Video ID`, `Video Name`, `Duration`, `Export Version`, …).
2. **Phases** — `Phase Name`, times, frames, `Description`, `Phaco Method`, …
3. **Skills & Ratings** — per-skill scores; aggregate footer rows filtered out.
4. **Comments & Notes** — typed markers with `Video Time` / text.
5. **Raw Data (Technical)** — full `Annotation Data (JSON)` blob (source of truth for replay / enrichment).

---

## 2. Internal persistence

- `cases` + `raw_payload` JSON.
- `case_phases`, `case_skills`, `case_comments`, `case_reports`.

---

## 3. Flags policy

Env: `SN_FLAG_POLICY` (default `phase_window_then_case_wide`), `SN_CONTRADICTION_SCORE_RATIO_THRESHOLD` (default `0.8`).

---

## 4. Report JSON schema (high level)

- `meta`: `schema_version`, **`report_locale`** (`en`|`fa`), `export_version`, `video_*`, `generated_at`, `sources`, thresholds.
- `sections.phase_summary.items`
- `sections.score_analysis`: `overall`, `per_skill_means`, **`score_narrative`** (template prose; language follows `meta.report_locale`)
- `sections.comments_timeline`
- `sections.contradictions.flags`
- `quality.limitations`

**Schema version** `1.3.0`: adds `meta.report_locale`. The `locale` parameter (`en` or `fa`) controls the language of template strings (`score_narrative`, limitations, case-wide flag `marker.notes`) in the generated report JSON. It also sets the default language for the Gemini narrative if no locale is explicitly provided to the narrative endpoint.

---

## 5. HTTP API (implemented)

| Method | Path | Notes |
|--------|------|--------|
| `POST` | `/v1/imports` | multipart `upload` file `.xlsx` / `.xlsm`; optional query `locale` (`en`|`fa`) sets `default_report_locale` echo (planning hint; not stored on case row). |
| `GET` | `/v1/cases/{case_id}` | normalized case + relations |
| `POST` | `/v1/cases/{case_id}/reports/generate` | query: `locale` (`en`|`fa`, default `SN_REPORT_LOCALE`), `persist` (default `true`). Generates JSON report with localized strings if `fa`. |
| `GET` | `/v1/cases/{case_id}/reports/latest` | last persisted report |
| `POST` | `/v1/narratives/generate` | body: `{ "report": {...}, "locale": "en"|"fa", ... }` + `GEMINI_API_KEY`. `locale` dictates Gemini output language. |
| `POST` | `/v1/narratives/generate-from-report` | body: **report JSON only** (same shape as `report` in `/reports/latest`); query `locale` (`en`|`fa`, default `SN_REPORT_LOCALE`), `include_provider_raw`, `extra_instructions`. Prefer **`curl`** from PowerShell (`ConvertTo-Json` brittle). |
| `POST` | `/v1/cases/{case_id}/narratives/generate` | same, pulls report from DB. Query `locale` (`en`|`fa`) overrides default. |
| `GET` | `/healthz` | liveness |

---

## 6. Project layout (this repo)

```
app/
  main.py
  config.py
  domain/
  application/ingest.py, analytics.py, report_pipeline.py, narrative.py
  infrastructure/excel/parser.py, database/*, llm/gemini_rest.py
  api/router.py, schemas.py, locale_util.py
tests/
scripts/smoke_test.ps1
CHECKLIST.md
docs/prompts/narrative_from_report_json.example.md
.env.example
```

### Run locally

```powershell
cd pre-task/2
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Environment (`.env` from `.env.example`)

- `SN_DATABASE_URL` — default `sqlite:///./data/surginote.db` (anchored under project root)
- `SN_REPORT_LOCALE` — `en`|`fa`; default structured-report + narrative `locale` when request omits it. Controls language of JSON template strings and Gemini output.
- `SN_CONTRADICTION_SCORE_RATIO_THRESHOLD` — default `0.8`
- `SN_FLAG_POLICY` — default `phase_window_then_case_wide`
- `GEMINI_API_KEY` / `GEMINI_MODEL` — for narrative endpoints

### Tests

```powershell
pytest tests -q
```

### Narrative from a saved report (`report_last.json`)

Use **`curl.exe`** with **`--data-binary @file`** so the server receives valid JSON. Example (after `smoke_test.ps1` or any flow that wrote `report_last.json`):

```powershell
curl.exe -sS -X POST "http://127.0.0.1:8000/v1/narratives/generate-from-report?locale=fa" `
  -H "Content-Type: application/json" `
  --data-binary "@.\report_last.json"
```

The older **`POST /v1/narratives/generate`** wrapper shape still works from clients that produce strict JSON (e.g. Python `httpx`, `curl` with a hand-built file).

---

## 7. Acceptance checklist

See **`CHECKLIST.md`** for the detailed tick list.

---

*README version `2.2` — spec prose in English; report JSON localized via `report_locale`.*
