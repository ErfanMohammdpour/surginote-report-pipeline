# Manual smoke: import xlsx -> generate report -> print JSON paths.
# Usage (from repo root pre-task/2):
#   .\scripts\smoke_test.ps1
#   .\scripts\smoke_test.ps1 -Xlsx "C:\Users\YOU\Downloads\annotation_export_case_4693_mp4 (3).xlsx"
# Requires: server running (uvicorn), curl.exe (Windows 10+).

param(
    [string] $BaseUrl = "http://127.0.0.1:8000",
    [string] $Xlsx = ""
)

$ErrorActionPreference = "Stop"

if (-not $Xlsx) {
    $minimal = Join-Path $PSScriptRoot "..\tests\_minimal_export.xlsx" | Resolve-Path
    if (Test-Path $minimal) {
        $Xlsx = $minimal.Path
    }
}
if (-not (Test-Path $Xlsx)) {
    Write-Error "No xlsx found. Pass -Xlsx path or ensure tests\_minimal_export.xlsx exists (run pytest once)."
}

Write-Host "== healthz" -ForegroundColor Cyan
curl.exe -sS "$BaseUrl/healthz"
Write-Host ""

Write-Host "== POST /v1/imports" -ForegroundColor Cyan
$importOut = curl.exe -sS -X POST "$BaseUrl/v1/imports" -F "upload=@$Xlsx"
Write-Host $importOut
$caseId = ($importOut | ConvertFrom-Json).case_id
if (-not $caseId) { Write-Error "No case_id in response" }

Write-Host "`n== GET /v1/cases/$caseId (truncated skills count)" -ForegroundColor Cyan
$caseJson = curl.exe -sS "$BaseUrl/v1/cases/$caseId" | ConvertFrom-Json
Write-Host ("phases: {0}, skills: {1}, comments: {2}" -f $caseJson.phases.Count, $caseJson.skills.Count, $caseJson.comments.Count)

Write-Host "`n== POST /v1/cases/$caseId/reports/generate" -ForegroundColor Cyan
$reportOut = curl.exe -sS -X POST "$BaseUrl/v1/cases/$caseId/reports/generate?persist=true"
$r = $reportOut | ConvertFrom-Json
Write-Host ("persisted_report_id: {0}" -f $r.persisted_report_id)

$flags = $r.report.sections.contradictions.flags
Write-Host ("flags count: {0}" -f @($flags).Count)

Write-Host "`n== meta (sample)" -ForegroundColor Cyan
$r.report.meta | ConvertTo-Json -Depth 5

Write-Host "`n== GET /v1/cases/$caseId/reports/latest (schema_version only)" -ForegroundColor Cyan
$latest = curl.exe -sS "$BaseUrl/v1/cases/$caseId/reports/latest" | ConvertFrom-Json
Write-Host ("latest persisted_report_id: {0}, schema in payload: {1}" -f $latest.persisted_report_id, $latest.report.meta.schema_version)

Write-Host "`nDone. Full last report JSON saved to: report_last.json" -ForegroundColor Green
$latest.report | ConvertTo-Json -Depth 20 | Set-Content -Path (Join-Path $PSScriptRoot "..\report_last.json") -Encoding UTF8
