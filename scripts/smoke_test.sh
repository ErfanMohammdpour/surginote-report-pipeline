#!/usr/bin/env bash
# End-to-end smoke test against running SurgiNote Report Service.
# Usage: ./scripts/smoke_test.sh
# Requires: server on http://127.0.0.1:8000, curl, python3

set -euo pipefail
BASE="${BASE_URL:-http://127.0.0.1:8000}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
XLSX="${XLSX:-$ROOT/tests/_minimal_export.xlsx}"

if [[ ! -f "$XLSX" ]]; then
  echo "Run: pytest tests -q   # creates tests/_minimal_export.xlsx"
  exit 1
fi

echo "== healthz / readyz"
curl -sS "$BASE/healthz"
echo
curl -sS "$BASE/readyz" | python3 -m json.tool
echo

echo "== POST /v1/imports (idempotent)"
KEY=$(python3 -c "import uuid; print(uuid.uuid4())")
IMPORT_JSON=$(curl -sS -w "\n%{http_code}" -X POST "$BASE/v1/imports" \
  -H "X-Idempotency-Key: $KEY" \
  -F "upload=@$XLSX")
HTTP_CODE=$(echo "$IMPORT_JSON" | tail -n1)
BODY=$(echo "$IMPORT_JSON" | sed '$d')
echo "HTTP $HTTP_CODE"
echo "$BODY" | python3 -m json.tool
if [[ "$HTTP_CODE" != "200" ]]; then
  echo "Import failed. If 503/500: enable SN_SKIP_OBJECT_STORAGE=true in .env and restart uvicorn."
  exit 1
fi

CASE_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['case_id'])")
IMPORT_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['import_id'])")
echo "case_id=$CASE_ID import_id=$IMPORT_ID"

echo "== GET /v1/cases/$CASE_ID"
curl -sS "$BASE/v1/cases/$CASE_ID" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('phases', len(d['phases']), 'skills', len(d['skills']), 'comments', len(d['comments']))
"

echo "== POST legacy report generate"
curl -sS -X POST "$BASE/v1/cases/$CASE_ID/reports/generate?persist=true" | python3 -c "
import sys,json
r=json.load(sys.stdin)
flags=r['report']['sections']['contradictions']['flags']
print('schema', r['report']['meta']['schema_version'], 'flags', len(flags))
"

echo "== audit-trail"
curl -sS "$BASE/v1/imports/$IMPORT_ID/audit-trail" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('total_events', d['total_events'], 'types', [e['event_type'] for e in d['events']])
"

echo "== POST async report"
REPORT_JSON=$(curl -sS -X POST "$BASE/v1/imports/$IMPORT_ID/reports/async")
echo "$REPORT_JSON" | python3 -m json.tool
REPORT_ID=$(echo "$REPORT_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['report_id'])")

echo "== report status"
curl -sS "$BASE/v1/reports/$REPORT_ID/status" | python3 -m json.tool

echo "== report payload (head)"
curl -sS "$BASE/v1/reports/$REPORT_ID" | python3 -c "
import sys,json
r=json.load(sys.stdin)
print('schema_version', r.get('schema_version'), 'sections', list(r.get('sections',{}).keys()))
"

echo "== idempotent replay"
REPLAY=$(curl -sS -D - -o /dev/null -X POST "$BASE/v1/imports" \
  -H "X-Idempotency-Key: $KEY" \
  -F "upload=@$XLSX" 2>&1 | grep -i x-idempotent-replay || true)
echo "${REPLAY:-no replay header}"

echo "Done."
