# Build delivery PDF from repo Template/ (XeLaTeX + xepersian — same as Template/main.tex workflow).
# Fonts: IRLotus + IranNastaliq from Template/font/ (per ARAS template layout).
# Usage (from repo root): .\scripts\compile_delivery_report.ps1

$ErrorActionPreference = "Stop"
$texDir = Join-Path $PSScriptRoot "..\Template" | Resolve-Path
Set-Location $texDir.Path
$env:PWD = $texDir.Path

xelatex -interaction=nonstopmode main.tex 2>&1 | Out-Null
xelatex -interaction=nonstopmode main.tex 2>&1 | Out-Null

$pdf = Join-Path $texDir.Path "main.pdf"
if (-not (Test-Path $pdf)) { Write-Error "main.pdf not produced. Run xelatex from Template/ and read main.log." }
Write-Host "OK: $pdf" -ForegroundColor Green
