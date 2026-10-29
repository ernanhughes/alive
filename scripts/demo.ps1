param([switch]$NoBuild)

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

& (Join-Path $PSScriptRoot 'init.ps1')
if ($LASTEXITCODE) { throw 'Local token initialization failed' }

$arguments = @('compose', 'up', '-d')
if (-not $NoBuild) { $arguments += '--build' }
& docker @arguments
if ($LASTEXITCODE) { throw 'docker compose up failed' }

Write-Host 'ALIVE demo started from this checkout. Use the token copied by scripts/init.ps1.'
Write-Host 'Stop it with: docker compose down'
