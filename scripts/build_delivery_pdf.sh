#!/usr/bin/env bash
# Build Persian delivery PDF (requires xelatex)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/Template"

if ! command -v xelatex >/dev/null 2>&1; then
  echo "Install texlive-xetex: sudo apt install texlive-xetex texlive-lang-other"
  exit 1
fi

xelatex -interaction=nonstopmode main.tex
xelatex -interaction=nonstopmode main.tex

cp -f main.pdf "$ROOT/SurgiNote_Report_Service_v3_delivery.pdf"
echo "PDF: $ROOT/SurgiNote_Report_Service_v3_delivery.pdf"
