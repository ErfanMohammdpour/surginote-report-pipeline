# Build delivery PDF: capture live API samples + compile LaTeX (Windows)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Base = "http://127.0.0.1:8000"
$Out = Join-Path $Root "Template\samples"
$Xlsx = Join-Path $Root "tests\_minimal_export.xlsx"
New-Item -ItemType Directory -Force -Path $Out | Out-Null

function Test-Server {
  try {
    $r = curl.exe -s -o NUL -w "%{http_code}" "$Base/healthz"
    return $r -eq "200"
  } catch { return $false }
}

if (-not (Test-Server)) {
  Write-Host "Starting uvicorn on :8000 ..."
  $env:SN_DATABASE_URL = "sqlite:///./data/delivery_capture.sqlite"
  $env:SN_SKIP_OBJECT_STORAGE = "true"
  $env:SN_SYNC_JOBS = "true"
  $py = if (Test-Path ".venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
  Start-Process -WindowStyle Hidden -FilePath $py -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000" -WorkingDirectory $Root
  for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Server) { break }
  }
  if (-not (Test-Server)) { throw "API not reachable on $Base" }
}

if (-not (Test-Path $Xlsx)) {
  $py = if (Test-Path ".venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
  & $py -m pytest tests/conftest.py -q | Out-Null
}

function Save-Json($obj, $path) {
  $obj | ConvertTo-Json -Depth 25 | Set-Content -Path $path -Encoding UTF8
}

Save-Json (curl.exe -s "$Base/readyz" | ConvertFrom-Json) "$Out\readyz.json"
$import = curl.exe -sS -X POST "$Base/v1/imports" -F "upload=@$Xlsx" | ConvertFrom-Json
Save-Json $import "$Out\import_response.json"
$impId = $import.import_id
$caseId = $import.case_id
Save-Json (curl.exe -sS "$Base/v1/imports/$impId/audit-trail" | ConvertFrom-Json) "$Out\audit_trail.json"
$async = curl.exe -sS -X POST "$Base/v1/imports/$impId/reports/async" | ConvertFrom-Json
Save-Json $async "$Out\async_report_start.json"
$rptId = $async.report_id
Save-Json (curl.exe -sS "$Base/v1/reports/$rptId/status" | ConvertFrom-Json) "$Out\report_status.json"
$report = curl.exe -sS "$Base/v1/reports/$rptId" | ConvertFrom-Json
$head = [ordered]@{
  report_id = $report.report_id
  schema_version = $report.schema_version
  generated_at = $report.generated_at
  source_import_id = $report.source_import_id
  locale = $report.locale
  section_keys = @($report.sections.PSObject.Properties.Name)
  metadata = $report.metadata
}
Save-Json $head "$Out\report_final_head.json"
$legacy = curl.exe -sS -X POST "$Base/v1/cases/$caseId/reports/generate?persist=false" | ConvertFrom-Json
Save-Json $legacy.report.meta "$Out\legacy_report_meta.json"
$py = if (Test-Path ".venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
(& $py -m pytest tests -q 2>&1 | Out-String).Trim() | Set-Content "$Out\pytest_output.txt" -Encoding UTF8

Write-Host "Building PDF..."
Set-Location (Join-Path $Root "Template")
$xelatex = "C:\Users\thisi\AppData\Local\Programs\MiKTeX\miktex\bin\x64\xelatex.exe"
if (-not (Test-Path $xelatex)) { $xelatex = "xelatex" }
& $xelatex -interaction=nonstopmode main.tex | Out-Null
& $xelatex -interaction=nonstopmode main.tex | Out-Null
Copy-Item main.pdf (Join-Path $Root "SurgiNote_Report_Service_v3_delivery.pdf") -Force
Write-Host "Done: $(Join-Path $Root 'SurgiNote_Report_Service_v3_delivery.pdf')"
