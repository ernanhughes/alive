param([switch]$Install)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
foreach ($port in @(8000, 5173)) {
    $socket = [System.Net.Sockets.TcpClient]::new()
    try { $socket.Connect('127.0.0.1', $port) } catch { }
    $inUse = $socket.Connected
    $socket.Dispose()
    if ($inUse) { throw "Port $port is already in use. Stop the existing process before starting ALIVE." }
}
if ($Install) {
    uv sync --locked
    Push-Location dashboard
    try { npm ci } finally { Pop-Location }
}
uv run alembic upgrade head
if ($LASTEXITCODE) { throw 'Migration failed' }
New-Item -ItemType Directory -Path .alive -Force | Out-Null
$backend = Start-Process -FilePath (Join-Path $PWD '.venv\Scripts\python.exe') -ArgumentList '-m','uvicorn','alive.app:app','--host','127.0.0.1','--port','8000' -WindowStyle Hidden -PassThru
$vitePath = Join-Path $PWD 'dashboard\node_modules\vite\bin\vite.js'
$dashboard = Start-Process -FilePath 'node' -ArgumentList @("`"$vitePath`"",'--host','127.0.0.1','--port','5173','--strictPort') -WorkingDirectory (Join-Path $PWD dashboard) -WindowStyle Hidden -PassThru
@{ backend = $backend.Id; dashboard = $dashboard.Id } | ConvertTo-Json | Set-Content .alive\dev-processes.json
foreach ($endpoint in @('http://127.0.0.1:8000/api/v1/health','http://127.0.0.1:5173')) {
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $endpoint -TimeoutSec 1
            if ($response.StatusCode -eq 200) { $ready = $true; break }
        } catch { }
        Start-Sleep -Milliseconds 250
    }
    if (-not $ready) {
        Stop-Process -Id $backend.Id,$dashboard.Id -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath .alive\dev-processes.json -ErrorAction SilentlyContinue
        throw "ALIVE startup did not become ready: $endpoint"
    }
}
Write-Host 'Dashboard: http://127.0.0.1:5173 | Backend: http://127.0.0.1:8000/docs'
Write-Host 'Read .alive/token locally to connect. Stop with ./scripts/stop.ps1'
