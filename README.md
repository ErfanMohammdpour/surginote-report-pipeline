# SurgiNote Report Service

**Production-ready** FastAPI service for surgical video annotation ingestion, analysis, and structured report generation. Designed for clinical and enterprise deployment.

---

## Workbook contract (`xlsx`)

1. **Video Info** — `Property | Value` rows (`Video ID`, `Video Name`, `Duration`, `Export Version`, …).
2. **Phases** — `Phase Name`, times, frames, `Description`, `Phaco Method`, …
3. **Skills & Ratings** — per-skill scores; aggregate footer rows filtered out.
4. **Comments & Notes** — typed markers with `Video Time` / text.
5. **Raw Data (Technical)** — full `Annotation Data (JSON)` blob (source of truth for replay / enrichment).

---

## Internal persistence

- `cases` + `raw_payload` JSON.
- `case_phases`, `case_skills`, `case_comments`, `case_reports`.
- `imports`, `import_events`, `idempotency_keys` — event store + audit trail.
- `reports`, `report_sections` — async pipeline reports (schema 2.0).

---

## Flags policy

Env: `SN_FLAG_POLICY` (default `phase_window_then_case_wide`), `SN_CONTRADICTION_SCORE_RATIO_THRESHOLD` (default `0.8`).

---

## Report JSON schema (high level)

- `meta`: `schema_version`, **`report_locale`** (`en`|`fa`), `export_version`, `video_*`, `generated_at`, `sources`, thresholds.
- `sections.phase_summary.items`
- `sections.score_analysis`: `overall`, `per_skill_means`, **`score_narrative`**
- `sections.comments_timeline`
- `sections.contradictions.flags`
- `quality.limitations`

---

## HTTP API

### Core import & case management

| Method | Path | Notes |
|--------|------|--------|
| `POST` | `/v1/imports` | multipart `upload` — `.xlsx`/`.xlsm`/`.json`/`.csv`; `X-Idempotency-Key`; SHA-256; audit events |
| `GET` | `/v1/cases/{case_id}` | normalized case + relations |
| `POST` | `/v1/cases/{case_id}/reports/generate` | query: `locale` (`en`|`fa`), `persist` (default `true`) |
| `GET` | `/v1/cases/{case_id}/reports/latest` | last persisted report |
| `POST` | `/v1/narratives/generate` | body: `{ "report": {...}, "locale": "en"|"fa" }` + `GEMINI_API_KEY` |
| `POST` | `/v1/narratives/generate-from-report` | body: report JSON; query: `locale`, `extra_instructions` |
| `POST` | `/v1/cases/{case_id}/narratives/generate` | pulls report from DB |
| `POST` | `/v1/reports/generate-ai` | **Task 5** — multi-agent AI clinical Markdown from `annotation_data` |
| `GET` | `/healthz` | liveness |
| `GET` | `/readyz` | DB readiness |

### Event pipeline & async reports

| Method | Path | Notes |
|--------|------|--------|
| `GET` | `/v1/imports/{id}/audit-trail` | append-only event log; `?format=csv` for CSV export |
| `POST` | `/v1/imports/{id}/reports/async` | 4-stage pipeline (ARQ or `SN_SYNC_JOBS=true`) |
| `GET` | `/v1/reports/{id}/status` | stage progress + `duration_ms` + `estimated_completion` |
| `GET` | `/v1/reports/{id}` | schema **2.0** final report |
| `GET` | `/v1/reports/{a}/diff/{b}` | deep diff across all sections |
| `POST` | `/v1/reports/{id}/regenerate` | rule/threshold override |
| `POST` | `/v1/webhooks` | register `report.completed` / `report.failed` / `import.completed` |

See **`docs/ARCHITECTURE.md`**, **`docs/AGENT_PIPELINE.md`**, and **`docker-compose.yml`** for service topology.

---

## AI clinical report pipeline (Task 5)

Generates a **supervisor-style Markdown evaluation** directly from platform `annotation_data` (phases, metrics, scores, markers) using a **5-agent LLM pipeline** with mandatory rule-based fallback.

### Endpoint

```http
POST /v1/reports/generate-ai
Content-Type: application/json
```

**Request body:** `phases`, `metrics`, `scores`, `markers`, optional `settings` (`tone` 0–4, `emphasis`, `locale`, `ai_config`).

**Response:** `{ "content": "<markdown>", "generatedAt": "<ISO8601>", "metadata": { ... } }`

See **`docs/AGENT_PIPELINE.md`** for architecture, metadata fields, and env vars. OpenAPI: `/docs` → `POST /v1/reports/generate-ai`.

### Quick curl (minimal fixture)

```bash
python3 - <<'PY'
import json, urllib.request
from pathlib import Path
body = json.loads(Path("tests/fixtures/annotation_data_minimal.json").read_text())
body["settings"] = {"tone": 2, "ai_config": {"enable_review": false}}
req = urllib.request.Request(
    "http://127.0.0.1:8000/v1/reports/generate-ai",
    data=json.dumps(body).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
print(json.load(urllib.request.urlopen(req))["metadata"])
PY
```

Without a live LLM key the orchestrator falls back to rule-based Markdown (`metadata.fallback_used=true`) — still HTTP 200.

### AI pipeline tests

```bash
pytest tests/unit/test_ai_pipeline/ --noconftest -q
pytest tests/integration/test_generate_ai_report.py -q
pytest tests/unit/test_ai_pipeline/ --noconftest \
  --cov=app/application/ai_pipeline --cov-fail-under=90
# or one shot:
./scripts/run_task5_tests.sh
```

---

## Architecture diagram

```mermaid
flowchart TD
    Client([HTTP Client])
    API["FastAPI\n(app/main.py)"]
    Router1["Core Router\n/v1/imports POST\n/v1/cases"]
    Router2["Pipeline Router\n/v1/imports/{id}/reports/async\n/v1/reports/{id}\n/v1/webhooks\n/v1/…/audit-trail"]
    Pipeline["import_pipeline.py\n(idempotency + sha256\n+ event sourcing)"]
    Parsers["multi.py\n(xlsx / json / csv)"]
    Validator["validation.py\n(JSON Schema 2020-12\n+ business rules)"]
    EventStore[("PostgreSQL\nimports, import_events\nidempotency_keys")]
    MinIO[("MinIO / S3\nraw files")]
    Redis[("Redis\nARQ queue")]
    Worker["ARQ Worker\n(report_pipeline)\nexp-backoff · independent stages"]
    Stage1["phase_summary"]
    Stage2["score_analysis"]
    Stage3["comment_timeline"]
    Stage4["contradictions\n(YAML rule engine)"]
    ReportDB[("PostgreSQL\nreports, report_sections")]
    Webhooks["webhooks.py\n(HMAC-SHA256 signing)"]
    Diff["report_diff.py\n(all-section deep diff)"]

    Client -->|multipart upload| API
    API --> Router1 & Router2
    Router1 --> Pipeline
    Pipeline --> Parsers & Validator & EventStore & MinIO
    Router2 -->|enqueue| Redis
    Redis --> Worker
    Worker --> Stage1 & Stage2 & Stage3 & Stage4
    Stage1 & Stage2 & Stage3 & Stage4 --> ReportDB
    ReportDB -->|final payload| Router2
    Router2 --> Diff
    ReportDB --> Webhooks
    Webhooks -->|POST + X-Signature-256| Client
```

---

## Project layout

```
app/
  main.py                  # ASGI app + middleware + lifespan
  config.py                # Pydantic settings (SN_* env vars)
  domain/                  # canonical, errors, events, hashing, security, validation
  application/             # import_pipeline, report_jobs, ai_pipeline/, report_diff, rules/
  infrastructure/          # database/, excel/, llm/, parsers/, queue/, secrets/, storage/
  api/                     # router.py (core), pipeline_router.py, errors.py, schemas.py
config/
  contradiction_rules.yaml
schemas/
  canonical.schema.json
tests/
  unit/                    # test_analyzers, test_rule_engine, test_security, test_validation
  integration/             # test_import_pipeline, test_edge_cases, test_security_features
scripts/
  smoke_test.sh
alembic/
  versions/001_initial_schema.py
docs/
  ARCHITECTURE.md
  AGENT_PIPELINE.md
docker-compose.yml
Dockerfile
.env.example
```

---

## Quick start (local)

```bash
docker compose up -d postgres redis minio
cp .env.example .env
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# async worker (skip with SN_SYNC_JOBS=true)
arq app.infrastructure.queue.worker.WorkerSettings
```

### Environment (`.env` from `.env.example`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `SN_DATABASE_URL` | PostgreSQL URL | Primary database |
| `SN_REDIS_URL` | `redis://localhost:6379/0` | ARQ queue |
| `SN_S3_ENDPOINT_URL` | `http://localhost:9000` | Object storage |
| `SN_REPORT_LOCALE` | `en` | `en`\|`fa` default report language |
| `SN_CONTRADICTION_SCORE_RATIO_THRESHOLD` | `0.8` | Flag threshold |
| `SN_FLAG_POLICY` | `phase_window_then_case_wide` | Detection scope |
| `GEMINI_API_KEY` | — | Narrative + AI pipeline (when `SN_AI_PROVIDER=gemini`) |
| `OPENAI_API_KEY` | — | AI pipeline when `SN_AI_PROVIDER=openai` |
| `SN_SYNC_JOBS` | `false` | Inline stages (dev/test) |
| `SN_SKIP_OBJECT_STORAGE` | `false` | Bypass MinIO (dev/test) |
| `SN_RATE_LIMIT` | `120/minute` | Per-IP rate limit |

### Task 5 AI pipeline (`SN_AI_*`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `SN_AI_PROVIDER` | `gemini` | Primary LLM (`gemini`, `openai`, `anthropic`, `ollama`; aliases `gpt`, `claude`) |
| `SN_AI_FALLBACK_PROVIDER` | — | Secondary provider if primary fails |
| `SN_AI_MODEL` | provider default | Model id (e.g. `gemini-2.5-flash`, `gpt-4o-mini`) |
| `SN_AI_TEMPERATURE` | `0.3` | Generation temperature |
| `SN_AI_MAX_TOKENS` | `2048` | Max tokens per LLM call |
| `SN_AI_TIMEOUT_SECONDS` | `60` | HTTP timeout for LLM adapters |
| `SN_AI_ENABLE_CACHE` | `true` | In-process LLM response cache |
| `SN_AI_CACHE_TTL_SECONDS` | `3600` | Cache entry TTL |
| `SN_AI_ENABLE_REVIEW` | `true` | Run Quality Reviewer agent |
| `SN_AI_MAX_PARALLEL` | `4` | Max concurrent phase analyzers |
| `SN_AI_MAX_RETRIES` | `2` | BaseAgent LLM retry count |

### Tests

```bash
pytest tests -q                           # all tests
pytest tests/unit -q                      # unit: rules, analyzers, validation, security
pytest tests/integration -q              # integration: pipeline, edge-cases, security
pytest tests --cov=app --cov-report=html  # coverage report
```

---

## Security

- Security headers on every response (`nosniff`, `X-Frame-Options: DENY`, XSS, Referrer-Policy)
- `X-Request-ID` tracing on every request
- Rate limiting per IP (`slowapi`)
- CORS configurable via `SN_CORS_ORIGINS`
- Filename sanitization: path traversal stripped, null bytes removed, 255-char cap
- Webhook secret: min 16 chars, HMAC-SHA256 signed outbound calls
- Secrets via `SN_SECRET_PROVIDER=env|mapped` (extend for Vault/AWS Secrets Manager)
- No internal details in 500 responses

---

*README v3.1 — Task 5 AI pipeline (`POST /v1/reports/generate-ai`) documented.*
