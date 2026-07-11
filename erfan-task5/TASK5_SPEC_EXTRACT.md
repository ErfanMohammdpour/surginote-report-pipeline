# Task 5 — Spec Extract (from تسک-5-عرفان.pdf)

**Pages:** 32 · **Source:** lead task document

---

## Agents (exactly 5)

| # | Agent | Prompt file | Parallel? |
|---|-------|-------------|-----------|
| 1 | Data Extractor & Normalizer | `prompts/data_extractor.txt` | No |
| 2 | Phase Analyzer | `prompts/phase_analysis.txt` | **Yes** — one instance per phase |
| 3 | Markers & Comments Analyzer | `prompts/markers_analysis.txt` | No |
| 4 | Report Composer | `prompts/report_composition.txt` | No |
| 5 | Quality Reviewer | `prompts/quality_review.txt` | Optional (`enable_review`) |

## Orchestrator flow

```
raw data → DataExtractor → PhaseAnalyzers (asyncio.gather) → MarkersAnalyzer
         → ReportComposer → QualityReviewer? → Markdown + metadata
         → on failure: fallback generate_clinical_report() from report_service.py
```

## Input schema (annotation_data)

From `GET /videos/{video_id}/annotation-history` — fields: `phases[]`, `metrics{}`, `scores{}`, `markers[]`, `version`, `savedAt`.

Marker fields: `id`, `type`, `timestamp`, `label`, `text`, `color`, `createdAt`.

Phase fields: `id`, `order`, `name`, `shortName`, `description`, `color`, `startTime`, `endTime`, `phacoMethod`, `source`.

## API (PDF)

- **Route:** `POST /reports/generate-ai`
- **Request:** phases, metrics, scores, markers, settings (tone, emphasis, ai_config)
- **Response:** content (Markdown), generatedAt, metadata (agents_used, tokens, confidence, fallback_used, cache_hits, quality_score)

## ai_config fields

```json
{
  "provider": "openai|anthropic|ollama|gemini",
  "model": "...",
  "temperature": 0.3,
  "enable_review": true,
  "enable_cache": true,
  "parallel_phases": true
}
```

## Mandatory deliverables (PDF §12)

| File | Purpose |
|------|---------|
| `ai_pipeline/__init__.py` | Package |
| `ai_pipeline/config.py` | Provider/model/temperature |
| `ai_pipeline/llm_client.py` | Unified LLM client |
| `ai_pipeline/base_agent.py` | BaseAgent abstract |
| `ai_pipeline/agents/*.py` | 5 agents |
| `ai_pipeline/orchestrator.py` | PipelineOrchestrator |
| `ai_pipeline/prompts/*.txt` | 5 prompt files |
| `ai_pipeline/cache.py` | LLM response cache |
| `ai_pipeline/token_manager.py` | Token counting/chunking |
| `ai_pipeline/utils.py` | parse_json_from_llm, retry_with_backoff, validate_llm_output |
| `routes.py` | Add endpoint |
| `report_schemas.py` | AISettings, AIReportResponse |
| `clinical_phrases.py` | Fallback phrases (**missing from codes/** — must create) |
| `sample_report_ai.md` | Sample output |
| `TASK5_REPORT.md` | Technical report |

## Mandatory test scenarios (PDF §9)

1. **Full data** — 3 phases + 4 markers, tone=2 → complete 5-section report
2. **Minimal** — 1 phase, no markers, tone=4 → short encouraging report
3. **Fallback** — no API key / network → rule-based, `fallback_used=true`
4. **Tone extremes** — same data tone 0 vs 4 → visibly different narrative

## Task 3 feedback → Task 5 fixes

| Was (Task 3) | Must be (Task 5) |
|--------------|------------------|
| Single monolithic LLM prompt | 5 specialized agents + txt prompts |
| Gemini only | Provider-agnostic LLMClient |
| No fallback | Mandatory rule-based fallback |
| No cache | LLMCache with SHA-256 key |
| No confidence | confidence_score per section + overall |
| Sequential | Parallel phase agents (asyncio) |
| Hardcoded prompts | prompts/*.txt files |

## Implementation order (PDF §31)

1. config.py + llm_client.py  
2. base_agent.py + prompts  
3. phase_analyzer.py (first full agent)  
4. orchestrator.py  
5. routes + tests  
6. cache + token_manager + optimization  

## Locale

PDF §14: **English first**; Persian extensible via config (Task 3 already has fa — implement en MVP, fa Phase 4+).

## Deadline

**Not stated in PDF** — confirm with lead.
