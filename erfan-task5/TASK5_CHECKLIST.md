# Task 5 — Master Checklist v4.0 (Final)

**Spec:** `erfan-task5/تسک-5-عرفان.pdf` (32 pages — fully reviewed)  
**Analysis:** `erfan-task5/TASK5_ANALYSIS.md`  
**Extract:** `erfan-task5/TASK5_SPEC_EXTRACT.md`  
**ADR:** `docs/AGENT_PIPELINE.md`  
**Repo:** [surginote-report-pipeline](https://github.com/ErfanMohammdpour/surginote-report-pipeline)

> **Rule:** Test-first (RED→GREEN→REFACTOR). Triple-check (§0) before every `[x]`. No live LLM in CI.

---

## §0 — Triple-check gate (mandatory)

Before marking **any** item complete:

- [x] **Pass 1 — Logic:** unit/integration tests for phases 0–4 pass; S1–S4 in `test_scenarios.py` + `test_generate_ai_report.py`  
- [x] **Pass 2 — Errors:** 6 agent exceptions + handlers + HTTP tests in `test_agent_errors.py`  
- [x] **Pass 3 — Regression:** `pytest tests/unit/test_ai_pipeline` + integration generate-ai green; Task 3 code untouched  
- [x] **Pass 4 — Quality:** type hints on public API; structured log per agent; no secrets in logs  

---

## §A — Architecture map (PDF → repo)

| PDF deliverable | Implementation path |
|-----------------|---------------------|
| `ai_pipeline/` | `app/application/ai_pipeline/` |
| `ai_pipeline/llm_client.py` | `app/infrastructure/llm/llm_client.py` |
| `ai_pipeline/agents/*.py` | `app/application/ai_pipeline/agents/` |
| `ai_pipeline/prompts/*.txt` | `app/application/ai_pipeline/prompts/` (5 files) |
| `report_service.py` | `app/application/ai_pipeline/fallback/report_service.py` |
| `clinical_phrases.py` | `app/application/ai_pipeline/fallback/clinical_phrases.py` |
| `POST /reports/generate-ai` | `POST /v1/reports/generate-ai` in `app/api/router.py` |
| Pydantic models | `app/application/ai_pipeline/schemas.py` + `app/api/schemas.py` |

**Do not modify:** `import_pipeline.py`, `report_jobs.STAGES`, `narrative.py`, `contradiction_rules.yaml` logic.

---

## §B — Five agents (PDF §5 — exact)

| # | Agent | Prompt file | Parallel |
|---|-------|-------------|----------|
| 1 | Data Extractor & Normalizer | `data_extractor.txt` | No |
| 2 | Phase Analyzer | `phase_analysis.txt` | **Yes** — `asyncio.gather` + semaphore `SN_AI_MAX_PARALLEL` |
| 3 | Markers & Comments Analyzer | `markers_analysis.txt` | No |
| 4 | Report Composer | `report_composition.txt` | No |
| 5 | Quality Reviewer | `quality_review.txt` | Optional (`SN_AI_ENABLE_REVIEW`) |

Output schemas: `TASK5_ANALYSIS.md` §5 (Pydantic models in `ai_pipeline/schemas.py`).

---

## §C — Error codes catalog

| `code` | HTTP | Exception class |
|--------|------|-----------------|
| `agent_error` | 400 | `AgentError` |
| `agent_validation_error` | 422 | `AgentValidationError` |
| `agent_input_error` | 422 | `AgentInputError` |
| `agent_output_parse_error` | 422 | `AgentOutputParseError` |
| `agent_upstream_error` | 502 | `AgentUpstreamError` |
| `agent_rate_limited` | 429 | `AgentRateLimitError` |
| `gemini_api_key_missing` | 400 | existing `ValueError` handler |
| fallback success | 200 | `metadata.fallback_used=true` — not an error |

Orchestrator: unrecoverable pipeline failure → `_fallback_to_rule_based()` — never bare 500.

---

## §D — Mandatory tests (PDF §9)

| ID | Fixture | tone | Key asserts | Status |
|----|---------|------|-------------|--------|
| S1 | `tests/fixtures/annotation_data_full_s1.json` | 2 | 5 report sections, 3 phases, metadata.confidence_score | ✅ orchestrator + integration |
| S2 | `tests/fixtures/annotation_data_minimal.json` | 4 | short, encouraging | ✅ orchestrator + integration |
| S3 | any + broken LLM mock | — | `fallback_used=true`, rule-based content | ✅ orchestrator + integration |
| S4 | S1 fixture | 0 vs 4 | narrative tone diff, same structure | ✅ orchestrator + integration |

Fixtures ready: `annotation_data_sample.json`, `annotation_data_full_s1.json`, `annotation_data_minimal.json`.

---

## Phase 0 — Spec ✅

- [x] **0.1** PDF 32 pages extracted and reviewed  
- [x] **0.2** `TASK5_ANALYSIS.md` v4  
- [x] **0.3** `TASK5_SPEC_EXTRACT.md`  
- [x] **0.4** Test fixtures S1, S2, sample  
- [x] **0.5** ADR `docs/AGENT_PIPELINE.md`  
- [x] **0.6** Architecture map §A  
- [ ] **0.7** Lead: deadline + confirm delivery in report-pipeline repo  

---

## Phase 1 — Foundation (PDF §31 steps 1–2) — TDD

### 1A — Domain & schemas

- [x] **1.1** `ai_pipeline/schemas.py` — all agent I/O Pydantic models (§5 in analysis)  
- [x] **1.2** `tests/unit/test_ai_pipeline/test_schemas.py` — validation edge cases  
- [x] **1.3** Extend `domain/errors.py` — 6 agent exception classes (§C)  
- [x] **1.4** Register handlers in `api/errors.py`  
- [x] **1.5** `tests/unit/test_ai_pipeline/test_agent_errors.py` — each code → HTTP  

### 1B — Utils & config

- [x] **1.6** `tests/unit/test_ai_pipeline/test_utils.py` — RED first  
- [x] **1.7** `ai_pipeline/utils.py` — `parse_json_from_llm`, `retry_with_backoff`, `validate_llm_output`  
- [x] **1.8** `ai_pipeline/config.py` — load `SN_AI_*` from settings  
- [x] **1.9** Extend `app/config.py` + `.env.example` with §9 env vars  

### 1C — LLM client

- [x] **1.10** `tests/unit/test_llm_client.py` — mock httpx  
- [x] **1.11** `infrastructure/llm/llm_client.py` — `chat()`, `count_tokens()`; gemini impl wraps `gemini_rest`  
- [x] **1.12** Stub adapters openai/anthropic/ollama raise `NotImplementedError` with clear message  
- [x] **1.13** Secondary provider fallback when configured  

### 1D — Base agent & prompts

- [x] **1.14** Create 5 prompt `.txt` files from PDF §5 system prompts  
- [x] **1.15** `tests/unit/test_ai_pipeline/test_base_agent.py`  
- [x] **1.16** `ai_pipeline/base_agent.py` — load prompt, `_call_llm`, max_retries=2, structured log  

### 1E — Fallback (rule-based)

- [x] **1.17** `fallback/clinical_phrases.py` — extract constants for report_service  
- [x] **1.18** Port `codes/report_service.py` → `fallback/report_service.py` (fix import path)  
- [x] **1.19** `tests/unit/test_ai_pipeline/test_fallback.py` — golden markdown snapshot S1  

---

## Phase 2 — Agents & orchestrator (PDF §31 steps 3–4) — TDD

For **each** agent: write test file first → implement → triple-check.

- [x] **2.1** `test_data_extractor.py` → `agents/data_extractor.py` (deterministic pre-validate + LLM)  
- [x] **2.2** `test_phase_analyzer.py` → `agents/phase_analyzer.py`  
- [x] **2.3** `test_markers_analyzer.py` → `agents/markers_analyzer.py`  
- [x] **2.4** `test_report_composer.py` → `agents/report_composer.py` (6-part Markdown structure)  
- [x] **2.5** `test_quality_reviewer.py` → `agents/quality_reviewer.py`  
- [x] **2.6** `test_orchestrator.py` — parallel, partial phase fail, full fallback, review retry  
- [x] **2.7** `orchestrator.py` — `PipelineOrchestrator.run()` async; metadata per PDF §8 response  
- [x] **2.8** Mock fixtures in `tests/fixtures/mock_llm_responses/` (one JSON per agent)  

---

## Phase 3 — API (PDF §31 step 5) — TDD

- [x] **3.1** `api/schemas.py` — `AIConfig`, `GenerateReportSettings`, `GenerateReportRequest`, `AIReportResponse`  
- [x] **3.2** `tests/integration/test_generate_ai_report.py` — S1, S2, S3, S4  
- [x] **3.3** `POST /v1/reports/generate-ai` in `router.py` — async orchestrator call  
- [x] **3.4** Rate limit (`app.state.limiter` + `SlowAPIMiddleware`) + security headers on all responses  
- [x] **3.5** Request validation: tone 0–4, non-empty phases, marker shape  

---

## Phase 4 — Optimization (PDF §31 step 6)

- [x] **4.1** `test_cache.py` → `ai_pipeline/cache.py` (key = agent+input+model+temp, TTL)  
- [x] **4.2** `test_token_manager.py` → `ai_pipeline/token_manager.py`  
- [x] **4.3** Wire cache into BaseAgent; increment `metadata.cache_hits`  
- [x] **4.4** Token counts in `metadata.tokens_used`  
- [x] **4.5** `scripts/smoke_test.sh` — generate-ai with mock or skip if no key  
- [x] **4.6** `pytest --cov=app/application/ai_pipeline --cov-fail-under=90` (unit `--noconftest`; integration separate)  

---

## Phase 5 — Delivery (PDF §12)

- [x] **5.1** `sample_report_ai.md` — full metadata block from PDF §8.3  
- [x] **5.2** `TASK5_REPORT.md` — technical report for lead  
- [x] **5.3** README — generate-ai section + env table  
- [x] **5.4** Re-index codebase-memory ADR  
- [x] **5.5** PR to `main` — `feat/task5-ai-pipeline`  

---

## §E — File tree (complete deliverable)

```
app/application/ai_pipeline/
  __init__.py
  config.py
  schemas.py
  base_agent.py
  orchestrator.py
  cache.py
  token_manager.py
  utils.py
  agents/
    data_extractor.py
    phase_analyzer.py
    markers_analyzer.py
    report_composer.py
    quality_reviewer.py
  prompts/
    data_extractor.txt
    phase_analysis.txt
    markers_analysis.txt
    report_composition.txt
    quality_review.txt
  fallback/
    report_service.py
    clinical_phrases.py
app/infrastructure/llm/
  llm_client.py          # new
  gemini_rest.py         # existing — used by llm_client
app/domain/errors.py     # extended
app/api/router.py        # + POST /v1/reports/generate-ai
app/api/schemas.py       # + AI models
tests/unit/test_ai_pipeline/   # 10+ test modules
tests/integration/test_generate_ai_report.py
tests/fixtures/            # S1, S2, sample, mock_llm_responses/
sample_report_ai.md
TASK5_REPORT.md
```

---

## §F — Time estimate

| Milestone | Days |
|-----------|------|
| Phase 1 complete (tests green) | 3 |
| Phase 2 complete | 4 |
| Phase 3 — S1–S4 pass | 2 |
| Phase 4–5 | 3 |
| **Total** | **12–13 working days** |

---

## §G — Lead questions (open)

1. ددلاین؟  
2. Provider production: Gemini یا OpenAI؟  
3. `enable_review` default true?  
4. تحویل فقط report-pipeline یا merge به main SurgiNote؟  

---

*Checklist v4.0 — PDF fully reviewed · test-first · triple-check · production error handling*
