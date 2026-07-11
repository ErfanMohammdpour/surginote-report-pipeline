# Task 5 — تحلیل فنی کامل (بر اساس PDF 32 صفحه)

**منبع:** `تسک-5-عرفان.pdf` · **Repo:** `surginote-report-pipeline` · **نسخه:** 4.0 · **تاریخ:** 2026-07-11

---

## 1. هدف تسک (یک جمله)

ساخت **پایپلاین ۵ Agent LLM** که `annotation_data` جراحی را بگیرد و **گزارش Markdown بالینی** تولید کند — با **fallback اجباری** به rule-based، **موازی‌سازی فازها**، **cache**، **confidence score**، و **۴ سناریو تست اجباری**.

---

## 2. آنچه Task 3 درست بود (تکرار کن — PDF §10)

| جنبه | فایل/ماژول |
|------|------------|
| لایه‌بندی Domain / Application / Infrastructure | `app/domain`, `application`, `infrastructure` |
| پایپلاین ۴ مرحله + ARQ | `report_jobs.py`, `worker.py` |
| Gemini REST بدون SDK | `gemini_rest.py` |
| Rule engine YAML | `contradiction_rules.yaml` |
| امنیت (HMAC, rate limit, sanitize) | `security.py`, `main.py`, `errors.py` |
| locale en/fa | `locale_util.py` |
| type hints + error handling لایه‌ای | الگوی `DomainError` → `api/errors.py` |

**Task 5 این‌ها را نشکند.** فقط `POST /v1/reports/generate-ai` اضافه شود.

---

## 3. آنچه Task 5 باید اصلاح کند (PDF §2, §11)

| مشکل Task 3 | راه‌حل Task 5 |
|-------------|--------------|
| یک پرامپت monolithic (`narrative.py`) | 5 Agent + 5 فایل `prompts/*.txt` |
| فقط Gemini | `LLMClient` — openai / anthropic / ollama / gemini |
| LLM down = خطا | `_fallback_to_rule_based()` → `generate_clinical_report()` |
| بدون cache | `LLMCache` — SHA-256, TTL 3600s |
| بدون confidence | `confidence_score` per phase + aggregate در metadata |
| sequential | `asyncio.gather` برای Phase Analyzer |
| markers فقط در rule engine | Agent 3 Markers Analyzer |
| بدون QA | Agent 5 Quality Reviewer |
| تست LLM محدود | 4 سناریو اجباری §9 |

---

## 4. معماری نهایی (سازگار با repo + PDF)

### 4.1 نگاشت مسیر

```
PDF (main app)                    surginote-report-pipeline
─────────────────────────────────────────────────────────────
report/ai_pipeline/          →    app/application/ai_pipeline/
report/ai_pipeline/llm_client →   app/infrastructure/llm/llm_client.py  ← HTTP boundary
report/report_service.py     →    app/application/ai_pipeline/fallback/report_service.py
report/clinical_phrases.py   →    app/application/ai_pipeline/fallback/clinical_phrases.py
report/routes.py             →    app/api/router.py
report/report_schemas.py     →    app/api/schemas.py + ai_pipeline/schemas.py
/reports/generate-ai         →    POST /v1/reports/generate-ai
```

### 4.2 لایه‌ها (قوانین وابستگی)

```
api/           → application/ai_pipeline, api/schemas — NEVER import llm_client directly
application/   → domain, infrastructure (via interface) — NO FastAPI imports
domain/        → فقط errors + validation helpers — NO httpx, NO LLM
infrastructure/→ httpx, env — implements LLMClient backends
```

### 4.3 جریان Orchestrator (دقیق PDF §17–21)

```
1. DataExtractor.process(raw)     → normalized | {error, normalized:null}
2. asyncio.gather(PhaseAnalyzer × N)  → List[PhaseAnalysis]  [PARALLEL — اجباری]
3. MarkersAnalyzer.process(markers)   → MarkersAnalysis
4. ReportComposer.process(...)        → {content: Markdown}
5. if enable_review:
     QualityReviewer.process(report)  → approved?, suggested_fixes
     if not approved: Composer retry once with fixes
6. return {content, metadata}
catch ANY unrecoverable:
     _fallback_to_rule_based()  → metadata.fallback_used=true
```

### 4.4 ساختار Markdown خروجی (هم‌تراز report_service.py)

PDF §9 می‌گوید «۵ بخش» — در `report_service.py` این‌ها هست:

1. Header — `# Surgical Procedure Evaluation Report`
2. Executive Summary — جدول آمار + پارagraph
3. Per-phase sections — جدول skill + narrative
4. Overall Assessment — strengths / weaknesses
5. Recommendations
6. Footer — disclaimer

Composer باید **همین ساختار** را تولید کند تا fallback و AI path **یکسان** به نظر برسند.

---

## 5. قرارداد هر Agent (JSON Schema — Pydantic)

### Agent 1 — Data Extractor

```python
class NormalizedData(BaseModel):
    normalized_phases: list[PhaseInput]
    normalized_markers: list[MarkerInput]
    metrics: dict[str, list[MetricInput]]
    scores: dict[str, dict[str, float]]
    metadata: dict[str, Any]

class ExtractorError(BaseModel):
    error: str
    normalized: None = None
```

**نکته پیاده‌سازی:** قبل از LLM، **validation deterministic** روی input — LLM فقط normalize/enrich. malformed → `ExtractorError` بدون burn token.

### Agent 2 — Phase Analyzer (هر فاز)

```python
class PhaseAnalysisOutput(BaseModel):
    phase_id: str
    clinical_narrative: str          # 2-4 sentences
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]
    key_insights: list[str]
    confidence_score: float = Field(ge=0, le=1)
```

### Agent 3 — Markers Analyzer

```python
class MarkersAnalysisOutput(BaseModel):
    commentary_insights: list[str]
    emotion_trend: Literal["positive", "negative", "neutral", "mixed"]
    critical_events: list[dict]
    alignment_with_scores: str
    confidence_score: float = Field(ge=0, le=1)
```

### Agent 4 — Report Composer

```python
class ComposerOutput(BaseModel):
    content: str  # full Markdown
    confidence_score: float = Field(ge=0, le=1)
```

### Agent 5 — Quality Reviewer

```python
class QualityReviewOutput(BaseModel):
    issues_found: list[str]
    suggested_fixes: list[str]
    overall_quality_score: float = Field(ge=0, le=1)
    approved: bool
```

---

## 6. Error handling — کامل (PDF §10 + Task 3 pattern)

### 6.1 Domain exceptions (`app/domain/errors.py`)

| Class | `code` | HTTP | When |
|-------|--------|------|------|
| `AgentError` | `agent_error` | 400 | base |
| `AgentValidationError` | `agent_validation_error` | 422 | Pydantic request fail |
| `AgentInputError` | `agent_input_error` | 422 | empty phases, bad tone |
| `AgentOutputParseError` | `agent_output_parse_error` | 422 | LLM JSON invalid after retries |
| `AgentUpstreamError` | `agent_upstream_error` | 502 | all providers failed |
| `AgentRateLimitError` | `agent_rate_limited` | 429 | 429 from provider |

### 6.2 سیاست retry (PDF BaseAgent: max_retries=2)

| Layer | Policy |
|-------|--------|
| `_call_llm` | 2 retry per call |
| `retry_with_backoff` in utils | exp backoff 1s, 2s, 4s |
| PhaseAnalyzer parallel | `return_exceptions=True` — یک فاز fail → template snippet برای همان فاز |
| Orchestrator total fail | fallback rule-based — **هرگز 500 بدون fallback** |
| QualityReviewer reject | 1 بار composer retry با `suggested_fixes` |

### 6.3 Response error shape (همیشه)

```json
{
  "code": "agent_validation_error",
  "message": "Human readable",
  "request_id": "uuid",
  "agent": "phase_analyzer",
  "phase_id": "phase_rhexis",
  "errors": [{"path": "...", "message": "..."}]
}
```

همه از `register_exception_handlers` — security headers روی همه (`_sec()`).

### 6.4 Logging (PDF §10.5)

```python
logger.info("agent=%s phase_id=%s latency_ms=%d tokens_in=%d tokens_out=%d cache_hit=%s",
            agent_name, phase_id, latency_ms, tokens_in, tokens_out, cache_hit)
```

**هرگز** log نکن: API key, full prompt, PHI در production.

---

## 7. استرategie تست (TDD — اول تست، بعد کد)

### 7.1 اصل

```
RED → GREEN → REFACTOR → Triple-check (§8)
```

**CI:** zero live LLM — mock `LLMClient.chat` in all tests.

### 7.2 ۴ سناریو اجباری (PDF §9)

| ID | Fixture | Settings | Assert |
|----|---------|----------|--------|
| **S1** | `annotation_data_full_s1.json` | tone=2 | `# Surgical Procedure`, Executive Summary, 3× `###`, Recommendations, `confidence_score` in metadata |
| **S2** | `annotation_data_minimal.json` | tone=4 | short report, encouraging keywords in narrative |
| **S3** | any + mock LLM raises | — | `fallback_used=true`, content matches rule-based golden |
| **S4** | `annotation_data_full_s1.json` | tone=0 vs 4 | same structure, different narrative tone (snapshot diff) |

### 7.3 ماتریس unit test

| Module | Tests |
|--------|-------|
| `utils.parse_json_from_llm` | valid JSON, markdown fence, trailing comma, empty |
| `utils.validate_llm_output` | schema match/mismatch |
| `utils.retry_with_backoff` | succeeds attempt 2, exhaust raises |
| `cache.LLMCache` | hit, miss, TTL expiry, key stability |
| `token_manager` | count, chunk split, warn threshold |
| `base_agent._call_llm` | retry, final raise |
| each `agents/*.py` | mock LLM returns fixture JSON |
| `orchestrator` | parallel call count, partial fail, full fallback, cache hit count |
| `llm_client` | gemini adapter, provider switch, secondary fallback |
| `fallback/report_service` | golden markdown S1 data |
| `api/errors` | each exception → status + code |

**Coverage gate:** `pytest --cov=app/application/ai_pipeline --cov-fail-under=90`

---

## 8. Triple-check gate (قبل از هر `[x]`)

| Pass | Checklist |
|------|-----------|
| **1 — Logic** | unit tests green for module; edge cases listed in §7.3 covered |
| **2 — Errors** | every `raise` has domain class + handler + test asserting `code` + HTTP status |
| **3 — Regression** | `pytest tests -q` full suite green; Task 3 import/narrative tests untouched |

**Bonus pass 4 — Code quality:** type hints, docstring on public methods, no `# noqa` without comment, ruff/mypy clean if configured.

---

## 9. Env variables (`SN_AI_*`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `SN_AI_PROVIDER` | `gemini` | primary provider |
| `SN_AI_FALLBACK_PROVIDER` | — | secondary if primary fails |
| `SN_AI_MODEL` | `gemini-2.5-flash` | model name |
| `SN_AI_TEMPERATURE` | `0.3` | generation |
| `SN_AI_MAX_TOKENS` | `2048` | per call cap |
| `SN_AI_TIMEOUT_SECONDS` | `60` | httpx timeout |
| `SN_AI_ENABLE_CACHE` | `true` | cache on/off |
| `SN_AI_CACHE_TTL_SECONDS` | `3600` | cache TTL |
| `SN_AI_ENABLE_REVIEW` | `true` | quality reviewer |
| `SN_AI_MAX_PARALLEL` | `4` | asyncio semaphore for phases |
| `SN_AI_MAX_RETRIES` | `2` | BaseAgent retries |
| `OPENAI_API_KEY` / `GEMINI_API_KEY` / … | — | per provider |

---

## 10. زمان‌بندی

| Phase | محتوا | روز |
|-------|--------|-----|
| 0 | PDF + ADR + fixtures | ✅ done |
| 1 | config, llm_client, base_agent, utils, fallback, prompts | 3 |
| 2 | 5 agents + orchestrator + unit tests | 4 |
| 3 | API schemas + endpoint + S1–S4 integration | 2 |
| 4 | cache, token_manager, coverage, smoke | 2 |
| 5 | sample_report_ai.md, TASK5_REPORT.md, PR | 1 |
| **جمع** | | **12–13 روز** |

---

## 11. Blocker باقی

| Item | Action |
|------|--------|
| `clinical_phrases.py` | Phase 1 — extract from report_service constants |
| Deadline | از لید بپرس (در PDF نیست) |
| merge به main app | تأیید لید — فعلاً report-pipeline |

---

## 12. تفاوت با checklist v3

| v3 | v4 |
|----|-----|
| error list کوتاه | catalog کامل + HTTP codes |
| test files listed | TDD workflow + S1–S4 fixtures ساخته شد |
| generic triple-check | 4-pass gate |
| composer sections vague | aligned با report_service 6-part structure |
| Data Extractor = LLM only | hybrid: deterministic validate first, LLM normalize |
| partial phase fail unclear | `return_exceptions=True` + per-phase template |

---

*تحلیل v4.0 — منبع: PDF کامل 32 صفحه + codes/ + Task 3 repo*
