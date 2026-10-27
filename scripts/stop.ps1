$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (Test-Path .alive\dev-processes.json) {
    $processes = Get-Content .alive\dev-processes.json | ConvertFrom-Json
    foreach ($processId in @($processes.backend, $processes.dashboard)) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$processId" -ErrorAction SilentlyContinue
        if ($process -and $process.CommandLine -match 'alive.app:app|vite[\\/]bin[\\/]vite.js') {
            Stop-Process -Id $processId -ErrorAction SilentlyContinue
        }
    }
    Remove-Item -LiteralPath .alive\dev-processes.json
}
