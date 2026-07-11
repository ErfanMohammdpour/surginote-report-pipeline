# Agent Pipeline ADR v2 — Task 5 (PDF-verified)

**Spec:** `erfan-task5/تسک-5-عرفان.pdf` (32 pages)  
**Analysis:** `erfan-task5/TASK5_ANALYSIS.md`  
**Status:** Phases 0–5 complete · delivered

## PURPOSE

Multi-agent LLM clinical Markdown report from SurgiNote `annotation_data`. Mandatory rule-based fallback. Provider-agnostic LLM. Test-first with 4 mandatory scenarios (S1–S4 covered at orchestrator level).

## STACK

| Component | Technology |
|-----------|------------|
| Agents | 5 — DataExtractor, PhaseAnalyzer×N, MarkersAnalyzer, ReportComposer, QualityReviewer |
| Orchestration | `PipelineOrchestrator` — asyncio, parallel phases, semaphore |
| LLM | `LLMClient` — gemini + openai impl; anthropic/ollama stubs |
| Fallback | `generate_clinical_report()` + `clinical_phrases.py` |
| Cache | `LLMCache` — SHA-256 key, TTL, wired in BaseAgent |
| API | `POST /v1/reports/generate-ai` |
| Tests | 90+ unit/integration tests, mocked LLM, S1–S4 |

## ARCHITECTURE

```
annotation_data → PipelineOrchestrator.run() [async]
  → DataExtractor (deterministic validate + optional LLM)
  → PhaseAnalyzer × N [asyncio.gather, semaphore SN_AI_MAX_PARALLEL]
  → MarkersAnalyzer
  → ReportComposer → 6-part Markdown validation
  → QualityReviewer? → composer retry once
  → on fail: fallback rule-based (never bare 500)
```

Task 3 unchanged: import, 4-stage ARQ, narratives, rule engine.

## PATTERNS

1. Prompts in `.txt` only  
2. One agent = one responsibility  
3. Parallel phase processing mandatory  
4. Fallback mandatory + safe double-fail message  
5. Validate LLM JSON — Pydantic + composer section check  
6. Gemini/OpenAI 429 → `AgentRateLimitError`  
7. Token counts in metadata  
8. TDD + triple-check gate (checklist §0)  

## ERROR HANDLING

Six domain exceptions → `api/errors.py`. Orchestrator never crashes without fallback attempt.

## OPEN

- [ ] Lead deadline (0.7)  
- [x] Phase 5 delivery docs + `sample_report_ai.md`  
