#!/usr/bin/env bash
# Task 5 AI pipeline — full test gate (no live LLM).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
echo "== unit (ai_pipeline)"
python3 -m pytest tests/unit/test_ai_pipeline/ --noconftest -q
echo "== integration (generate-ai)"
python3 -m pytest tests/integration/test_generate_ai_report.py -q
echo "== coverage gate"
python3 -m pytest tests/unit/test_ai_pipeline/ --noconftest \
  --cov=app/application/ai_pipeline --cov-fail-under=90 -q
echo "Task 5 tests OK."
