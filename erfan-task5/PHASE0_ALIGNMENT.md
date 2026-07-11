# Phase 0 — Spec & Alignment Tracker (v4)

**Started:** 2026-07-11  
**Owner:** Erfan  
**Checklist:** `TASK5_CHECKLIST.md` v4  
**Analysis:** `TASK5_ANALYSIS.md` v4

---

## Status summary

| ID | Item | Status | Notes |
|----|------|--------|-------|
| 0.1 | 32-page task PDF | ✅ DONE | `erfan-task5/تسک-5-عرفان.pdf` |
| 0.2 | alongside vs replace `/v1/narratives/*` | ✅ LOCKED | **Alongside** — Task 3 unchanged |
| 0.3 | Agent roster | ✅ LOCKED | **Exactly 5** per PDF §5 (not 7–8 provisional) |
| 0.4 | LLM provider | ✅ DEFAULT | **Gemini first** — `LLMClient` multi-provider |
| 0.5 | Locales | ✅ DEFAULT | **en MVP** — fa via config later (PDF §14) |
| 0.6 | annotation_data fixtures | ✅ DONE | S1, S2, sample in `tests/fixtures/` |
| 0.7 | ADR | ✅ DONE | `docs/AGENT_PIPELINE.md` v2 + codebase-memory |
| 0.8 | Lead deadline | ☐ OPEN | Ask lead |

**Phase 0 gate:** ✅ Complete — Phase 1 may start.

---

## Decisions locked (PDF-verified)

### D1 — Endpoint

- **Primary:** `POST /v1/reports/generate-ai` (PDF `/reports/generate-ai` + Task 3 `/v1` prefix)
- **Keep:** all `/v1/narratives/*`, `/v1/imports`, async report stages

### D2 — Input contract

Direct `annotation_data` from platform API shape:

`phases[]`, `metrics{}`, `scores{}`, `markers[]`, `version`, `savedAt`

Settings: `tone` 0–4, `emphasis[]`, `ai_config` (provider, model, temperature, enable_review, enable_cache, parallel_phases)

### D3 — Output contract

6-part Markdown aligned with `report_service.py`:

Header → Executive Summary → Per-phase → Overall Assessment → Recommendations → Footer

Metadata: `pipeline`, `agents_used`, `model`, `tokens_used`, `generation_time_seconds`, `confidence_score`, `fallback_used`, `cache_hits`, `quality_score`

### D4 — Agent roster (PDF §5 — final)

| # | Agent | Prompt |
|---|-------|--------|
| 1 | Data Extractor & Normalizer | `data_extractor.txt` |
| 2 | Phase Analyzer (×N parallel) | `phase_analysis.txt` |
| 3 | Markers & Comments Analyzer | `markers_analysis.txt` |
| 4 | Report Composer | `report_composition.txt` |
| 5 | Quality Reviewer (optional) | `quality_review.txt` |

### D5 — Fallback

Mandatory `_fallback_to_rule_based()` → `generate_clinical_report()` + `clinical_phrases.py` (create Phase 1.17)

### D6 — Testing

TDD + triple-check gate (4-pass). S1–S4 mandatory. No live LLM in CI. ≥90% coverage on `ai_pipeline/`.

### D7 — Timeline

| Scope | Days |
|-------|------|
| Phase 1–3 (MVP + S1–S4) | 9 |
| Phase 4–5 (cache, delivery) | 3–4 |
| **Total production** | **12–13** |

---

## Lead message (updated — Persian)

```
سلام، وقت بخیر.

Phase 0 کامل شد:

✅ PDF 32 صفحه بررسی شد
✅ معماری 5 Agent + fallback + parallel phases
✅ ADR و تحلیل v4 + چک‌لیست v4
✅ fixture تست S1/S2/sample
✅ endpoint: POST /v1/reports/generate-ai

⏳ نیاز به تأیید:
1. ددلاین دقیق
2. Provider production: Gemini یا OpenAI؟
3. enable_review پیش‌فرض true؟
4. تحویل فقط report-pipeline یا merge به main SurgiNote؟

تخمین: 12–13 روز کاری برای production با تست کامل.

Phase 1 (foundation + TDD) آماده شروع است.
```

---

## Phase 0 exit criteria

- [x] Task PDF received and reviewed
- [x] Agent list reconciled (5 agents)
- [x] ADR written and stored
- [x] Test fixtures S1, S2, sample
- [x] Architecture map PDF → repo
- [x] Error catalog + triple-check gate documented
- [ ] Lead confirms deadline + provider + delivery target

**→ Phase 1 start:** now (no blocker except lead preferences)

---

## Removed (v2 provisional — superseded)

- ~~8-agent roster (Deterministic, Executive, Assessment, …)~~
- ~~`POST /v1/cases/{case_id}/agent-report/generate`~~
- ~~PDF blocked~~

---

*Last updated: 2026-07-11 — v4 aligned with PDF + TASK5_ANALYSIS.md*
