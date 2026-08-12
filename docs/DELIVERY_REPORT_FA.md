# گزارش تحویل — SurgiNote Report Service v3.0

**عرفان محمدپور** · ARAS · اردیبهشت ۱۴۰۵  
**مخزن:** https://github.com/ErfanMohammdpour/surginote-report-pipeline (خصوصی)

---

## ۱. خلاصه

سرویس آمادهٔ استقرار برای ورود فایل SurgiNote، ذخیرهٔ رویدادمحور، گزارش همگام (schema 1.3.0) و گزارش ناهمگام چهارمرحله‌ای (schema 2.0).

| مورد | مقدار |
|------|--------|
| نسخه API | 3.0.0 |
| تست‌ها | 48 passed |
| پوشش کد | ~78% |
| OpenAPI | 3.1 — `/docs` |

---

## ۲. Swagger UI

![Swagger 3.0](../Template/img/swagger.png)

**۱۳ اندپوینت:** imports، cases، reports (legacy + async)، narratives، webhooks، diff، regenerate.

---

## ۳. نمونه خروجی‌ها (اجرای واقعی)

### GET /readyz

```json
{
  "ok": true,
  "database": "up"
}
```

### POST /v1/imports

```json
{
  "case_id": "0ff0e52b-7fc2-4431-bb5b-ace89768a8c9",
  "import_id": "imp_09011020208e",
  "warnings": [],
  "default_report_locale": "en",
  "file_hash_sha256": "b03b2846b46d81aac725342304e7939d840944daa9075a096cd9633f59de2fed",
  "format": "xlsx"
}
```

### GET /v1/imports/{id}/audit-trail

```json
{
  "import_id": "imp_09011020208e",
  "total_events": 4,
  "events": [
    { "event_type": "ImportStarted" },
    { "event_type": "ValidationCompleted" },
    { "event_type": "NormalizationCompleted" },
    { "event_type": "StorageCompleted" }
  ]
}
```

### POST /v1/imports/{id}/reports/async

```json
{
  "report_id": "rpt_7882418d43dd",
  "status": "completed",
  "progress_percent": 100,
  "async": false
}
```

### GET /v1/reports/{id}/status

```json
{
  "report_id": "rpt_7882418d43dd",
  "status": "completed",
  "progress_percent": 100,
  "completed_stages": [
    { "name": "phase_summary", "duration_ms": 2 },
    { "name": "score_analysis", "duration_ms": 2 },
    { "name": "comment_timeline", "duration_ms": 2 },
    { "name": "contradictions", "duration_ms": 2 }
  ],
  "duration_ms": 173
}
```

### GET /v1/reports/{id} (سرآیند schema 2.0)

```json
{
  "report_id": "rpt_7882418d43dd",
  "schema_version": "2.0",
  "sections": ["phase_summary", "score_analysis", "comment_timeline", "contradictions"],
  "metadata": {
    "processing_time_ms": 173,
    "stages_executed": 4,
    "stages_failed": 0,
    "total_events_processed": 4
  }
}
```

### Legacy report meta (schema 1.3.0)

```json
{
  "schema_version": "1.3.0",
  "report_locale": "en",
  "export_version": "9.9",
  "video_name": "unit.xlsx",
  "duration_seconds": 120.0,
  "flag_policy": "phase_window_then_case_wide"
}
```

**Smoke:** `phases 1 skills 1 comments 1` · `flags 1`

### Idempotency

```
X-Idempotent-Replay: true
```

### pytest

```
48 passed in ~20s
```

### smoke_test.sh

```
healthz/readyz OK · import HTTP 200 · audit 4 events · report 100% · replay OK · Done.
```

---

## ۴. PDF فارسی (LaTeX)

```bash
sudo apt install -y texlive-xetex texlive-lang-other
./scripts/build_delivery_pdf.sh
```

خروجی: `SurgiNote_Report_Service_v3_delivery.pdf`

فایل‌های LaTeX: `Template/main.tex` + `surginote_body.tex` + `samples/`

---

## ۵. اجرا و تست

```bash
./scripts/smoke_test.sh
pytest tests -q
```
