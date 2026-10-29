<#
ALIVE-DEMO-INTEGRATION-01 clean-volume acceptance (Windows PowerShell / pwsh).

Builds the composed app from this checkout under a DISPOSABLE compose project, so it never touches
your own `alive_*` volumes, then drives the demonstration in real Chrome:
  1. clean volumes -> up --build -> smoke test
  2. journey (Start, every step, reload, second run, owner data untouched)
  3. `docker compose restart app`            -> after-restart checks (new process id, same state)
  4. `docker compose down` then `up -d`      -> after-restart checks again (volumes survived)
  5. ALIVE_DEMO_MODE=false                    -> the tab refuses, API says 403
No provider key is set and no paid call is possible. Needs Docker, uv, Node and Chrome.

  pwsh scripts/demo-acceptance.ps1 [-Project alive-demo-accept] [-Port 8000] [-Record] [-KeepRunning]

The web demonstration works on any free host port; only the Chrome-extension lane needs 8000.
#>
param(
  [string]$Project = "alive-demo-accept",
  [int]$Port = 8000,
  [switch]$Record,
  [switch]$KeepRunning
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:ALIVE_API_TOKEN = "alive-dev-token-replace-for-local-use-000"
$env:ALIVE_HOST_PORT = "$Port"
$env:ALIVE_BASE_URL = "http://localhost:$Port"
$env:DEMO_E2E = "1"
$env:DEMO_STATE_FILE = Join-Path $root ".alive/demo-acceptance/state.json"
$evidence = Join-Path $root "docs/demo/evidence"

function Step($name, [scriptblock]$block) {
  Write-Host "`n=== $name ===" -ForegroundColor Cyan
  & $block
  if ($LASTEXITCODE -ne 0) { throw "FAILED: $name (exit $LASTEXITCODE)" }
}
function Wait-Healthy {
  for ($i = 0; $i -lt 60; $i++) {
    $state = docker compose -p $Project ps --format '{{.Service}} {{.Health}}' | Select-String '^app'
    if ($state -and "$state" -match 'healthy') { return }
    Start-Sleep -Seconds 3
  }
  throw "app did not become healthy"
}
function Phase($phase) {
  $env:DEMO_PHASE = $phase
  Push-Location (Join-Path $root "dashboard")
  try { npx playwright test e2e/demo-tour.spec.ts --reporter=list } finally { Pop-Location }
}

$busy = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($busy) { throw "Host port $Port is in use by pid $($busy[0].OwningProcess); pass -Port <free port>" }
Step "commit under test" { git rev-parse HEAD; $global:LASTEXITCODE = 0 }
Step "clean volumes (disposable project only)" { docker compose -p $Project down -v --remove-orphans }
Remove-Item -Recurse -Force (Split-Path $env:DEMO_STATE_FILE) -ErrorAction SilentlyContinue
Step "build and start" { docker compose -p $Project up --build -d }
Wait-Healthy
Step "dashboard dependencies" { Push-Location dashboard; npm ci --no-audit --no-fund; $c = $LASTEXITCODE; Pop-Location; $global:LASTEXITCODE = $c }
Step "smoke test" { uv run python scripts/docker-smoke-test.py }
Step "journey in Chrome" { Phase "journey" }
Step "restart the app container (volumes kept)" { docker compose -p $Project restart app }
Wait-Healthy
Step "after restart" { Phase "after-restart" }
Step "remove containers and start again (volumes kept)" { docker compose -p $Project down; docker compose -p $Project up -d }
Wait-Healthy
Step "after down/up" { Phase "after-restart" }
if ($Record) { Step "recorded walkthrough" { Phase "record" } }
$env:ALIVE_DEMO_MODE = "false"
Step "demo mode off" { docker compose -p $Project up -d app }
Wait-Healthy
Step "disabled" { Phase "disabled" }
Remove-Item Env:ALIVE_DEMO_MODE
if (-not $KeepRunning) { Step "teardown (disposable project)" { docker compose -p $Project down -v } }
Write-Host "`nACCEPTANCE OK. Screenshots: $evidence" -ForegroundColor Green
