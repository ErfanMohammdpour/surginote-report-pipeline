#!/usr/bin/env bash
# Capture JSON samples for LaTeX delivery report (server must be running on :8000)
set -euo pipefail
BASE="${BASE_URL:-http://127.0.0.1:8000}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/Template/samples"
XLSX="${XLSX:-$ROOT/tests/_minimal_export.xlsx}"

mkdir -p "$OUT"
curl -sS "$BASE/readyz" | python3 -m json.tool > "$OUT/readyz.json"

IMPORT=$(curl -sS -X POST "$BASE/v1/imports" -F "upload=@$XLSX")
echo "$IMPORT" | python3 -m json.tool > "$OUT/import_response.json"
IMP_ID=$(echo "$IMPORT" | python3 -c "import sys,json; print(json.load(sys.stdin)['import_id'])")
CASE_ID=$(echo "$IMPORT" | python3 -c "import sys,json; print(json.load(sys.stdin)['case_id'])")

curl -sS "$BASE/v1/imports/$IMP_ID/audit-trail" | python3 -m json.tool > "$OUT/audit_trail.json"
curl -sS -X POST "$BASE/v1/imports/$IMP_ID/reports/async" | python3 -m json.tool > "$OUT/async_report_start.json"
RPT_ID=$(curl -sS -X POST "$BASE/v1/imports/$IMP_ID/reports/async" | python3 -c "import sys,json; print(json.load(sys.stdin)['report_id'])")
curl -sS "$BASE/v1/reports/$RPT_ID/status" | python3 -m json.tool > "$OUT/report_status.json"
curl -sS "$BASE/v1/reports/$RPT_ID" | python3 -c "
import sys,json
r=json.load(sys.stdin)
head={k:r[k] for k in ('report_id','schema_version','generated_at','source_import_id','locale','sections','metadata') if k in r}
print(json.dumps(head, indent=2))
" > "$OUT/report_final_head.json"

curl -sS -X POST "$BASE/v1/cases/$CASE_ID/reports/generate?persist=false" | python3 -c "
import sys,json
m=json.load(sys.stdin)['report']['meta']
print(json.dumps(m, indent=2))
" > "$OUT/legacy_report_meta.json"

echo "Samples written to $OUT"
