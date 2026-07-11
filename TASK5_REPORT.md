# Task 5 — Technical Delivery Report

**Project:** SurgiNote Report Service — Multi-Agent AI Clinical Report Pipeline  
**Spec:** `erfan-task5/تسک-5-عرفان.pdf` (32 pages)  
**Repository:** [surginote-report-pipeline](https://github.com/ErfanMohammdpour/surginote-report-pipeline)  
**Author:** Erfan Mhp · **Date:** 2026-07-11  
**Status:** Phases 0–5 complete

---

## 1. Executive summary

Task 5 adds a **five-agent LLM pipeline** that converts SurgiNote `annotation_data` into a **clinical Markdown evaluation report**, exposed as `POST /v1/reports/generate-ai`. The design is production-oriented: provider-agnostic LLM access, parallel phase analysis, in-process response cache, mandatory rule-based fallback, structured metadata, rate limiting, and **90%+ test coverage** on the AI pipeline module.

Task 3 functionality (import pipeline, ARQ async reports, narratives, rule engine) is **unchanged**.

---

## 2. Deliverables checklist

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 0 | PDF review, fixtures, ADR | ✅ |
| 1 | Config, LLM client, base agent, utils, fallback, prompts | ✅ |
| 2 | 5 agents + orchestrator + unit tests | ✅ |
| 3 | API schemas + `POST /v1/reports/generate-ai` + S1–S4 integration | ✅ |
| 4 | Cache, token manager, smoke test, coverage ≥90% | ✅ |
| 5 | Sample report, this document, README, ADR re-index | ✅ |

**Master checklist:** `erfan-task5/TASK5_CHECKLIST.md`  
**Deep analysis:** `erfan-task5/TASK5_ANALYSIS.md`

---

## 3. Architecture

```
POST /v1/reports/generate-ai
  → run_ai_report (service.py)
  → PipelineOrchestrator.run() [async]
       1. DataExtractor      — deterministic validate + optional LLM enrich
       2. PhaseAnalyzer × N  — asyncio.gather + semaphore (SN_AI_MAX_PARALLEL)
       3. MarkersAnalyzer
       4. ReportComposer     — 6-part Markdown validation
       5. QualityReviewer?   — optional; composer retry once if rejected
       → on failure: generate_clinical_report() (rule-based fallback)
```

**Layering (unchanged Task 3 rules):**

- `app/api/` — HTTP only; calls `application/ai_pipeline/service.py`
- `app/application/ai_pipeline/` — agents, orchestrator, cache, fallback
- `app/infrastructure/llm/` — `LLMClient` + provider adapters (Gemini, OpenAI; Anthropic/Ollama stubs)

**ADR:** `docs/AGENT_PIPELINE.md`

---

## 4. API contract

### Request

`POST /v1/reports/generate-ai`

Body: `annotation_data` + settings (PDF §8).

```json
{
  "phases": [{ "id": "phase_rhexis", "name": "Rhexis", "startTime": 30, "endTime": 125 }],
  "metrics": { "phase_rhexis": [{ "id": "m1", "name": "Centration", "maxScore": 5 }] },
  "scores": { "phase_rhexis": { "m1": 4.0 } },
  "markers": [{ "id": "m1", "type": "comment", "timestamp": 45.0, "text": "Smooth tear" }],
  "settings": {
    "tone": 2,
    "emphasis": ["technical", "safety"],
    "locale": "en",
    "ai_config": {
      "provider": "gemini",
      "enable_review": true,
      "enable_cache": true,
      "parallel_phases": true
    }
  }
}
```

**Validation:** tone 0–4, ≥1 phase, marker types `comment|warning|audio|event`, required marker `timestamp`.

### Response (PDF §8.3)

```json
{
  "content": "# Surgical Procedure Evaluation Report\n...",
  "generatedAt": "2026-07-11T01:04:59Z",
  "metadata": {
    "pipeline": "ai-agent-v2",
    "agents_used": ["data_extractor", "phase_analyzer(3 parallel instances)", "..."],
    "model": "gemini-2.5-flash",
    "tokens_used": { "input": 60, "output": 90, "total": 150 },
    "generation_time_seconds": 0.42,
    "confidence_score": 0.9,
    "fallback_used": false,
    "fallback_reason": null,
    "cache_hits": 0,
    "quality_score": 0.95
  }
}
```

**Sample artifact:** `sample_report_ai.md`

---

## 5. LLM provider switch

Set **`SN_AI_PROVIDER`** (or per-request `ai_config.provider`):

| Tag | Provider |
|-----|----------|
| `gemini` (default) | Google Gemini REST |
| `openai`, `gpt`, `chatgpt` | OpenAI |
| `anthropic`, `claude` | Stub adapter |
| `ollama` | Local stub |

Optional **`SN_AI_FALLBACK_PROVIDER`** for primary failure retry.

---

## 6. Testing

| Suite | Command | Notes |
|-------|---------|-------|
| AI unit | `pytest tests/unit/test_ai_pipeline/ --noconftest -q` | Mock LLM only |
| AI integration | `pytest tests/integration/test_generate_ai_report.py -q` | S1–S4 + validation |
| Coverage gate | `pytest tests/unit/test_ai_pipeline/ --noconftest --cov=app/application/ai_pipeline --cov-fail-under=90` | **91%+** |
| Smoke (live server) | `./scripts/smoke_test.sh` | Includes generate-ai; skip with `SN_SKIP_AI_SMOKE=true` |

**Mandatory scenarios (PDF §9):** S1 full, S2 minimal, S3 fallback, S4 tone extremes — covered at orchestrator and HTTP layers.

---

## 7. Security & ops

- Security headers on all responses (`nosniff`, `X-Frame-Options`, etc.)
- `X-Request-ID` tracing
- Rate limit via `slowapi` + `SN_RATE_LIMIT` (default `120/minute`)
- Orchestrator **never returns bare 500** for pipeline failure — rule-based fallback with `fallback_used=true`
- Agent domain errors mapped in `app/api/errors.py` (429 rate limit, 502 upstream, 422 validation)

---

## 8. File map (new / modified)

```
app/application/ai_pipeline/     # agents, orchestrator, cache, token_manager, fallback
app/infrastructure/llm/          # LLMClient, types, providers
app/api/router.py                # POST /v1/reports/generate-ai
app/api/schemas.py               # GenerateReportRequest, AIReportResponse
tests/unit/test_ai_pipeline/     # 15+ test modules
tests/integration/test_generate_ai_report.py
tests/fixtures/                  # S1, S2, mock_llm_responses
sample_report_ai.md
docs/AGENT_PIPELINE.md
```

---

## 9. Open questions for lead (§G)

1. **Deadline** for production rollout?
2. **Production provider** — Gemini or OpenAI?
3. **`enable_review` default** — keep `true` (current env default)?
4. **Delivery target** — this repo only, or merge into main SurgiNote monolith?

---

## 10. How to run locally

```bash
cp .env.example .env          # set GEMINI_API_KEY or OPENAI_API_KEY
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

curl -sS -X POST http://127.0.0.1:8000/v1/reports/generate-ai \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/annotation_data_minimal.json
```

See **README.md** for full env table and smoke test instructions.

---

*Task 5 technical report · aligned with PDF §12 delivery requirements*
