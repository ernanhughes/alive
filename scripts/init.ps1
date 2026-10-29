[CmdletBinding()]
param(
    [switch]$Rotate,
    [switch]$NoClipboard,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    $envPath = Join-Path $root '.env'
    $examplePath = Join-Path $root '.env.example'
    $stateDir = Join-Path $root '.alive'
    $tokenPath = Join-Path $stateDir 'token'
    $utf8 = New-Object System.Text.UTF8Encoding($false)

    function Test-Token([string]$value) {
        if ([string]::IsNullOrWhiteSpace($value)) { return $false }
        if ($value.Length -lt 24) { return $false }
        foreach ($ch in $value.ToCharArray()) {
            $code = [int]$ch
            if ($code -lt 33 -or $code -gt 126) { return $false }
        }
        return $true
    }

    function Test-Placeholder([string]$value) {
        return $value -match '^(replace|change|example|your[-_])'
    }

    function Get-EnvToken([string]$path) {
        if (-not (Test-Path -LiteralPath $path)) { return $null }
        foreach ($line in [IO.File]::ReadAllLines($path)) {
            if ($line -match '^\s*ALIVE_API_TOKEN\s*=\s*(.*)$') {
                $value = $Matches[1].Trim()
                if ($value.Length -ge 2) {
                    $first = $value.Substring(0, 1)
                    $last = $value.Substring($value.Length - 1, 1)
                    if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
                        $value = $value.Substring(1, $value.Length - 2)
                    }
                }
                return $value
            }
        }
        return $null
    }

    function Set-EnvToken([string]$path, [string]$token) {
        $lines = New-Object 'System.Collections.Generic.List[string]'
        if (Test-Path -LiteralPath $path) {
            $lines.AddRange([string[]][IO.File]::ReadAllLines($path))
        }
        $found = $false
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match '^\s*ALIVE_API_TOKEN\s*=') {
                if (-not $found) {
                    $lines[$i] = "ALIVE_API_TOKEN=$token"
                    $found = $true
                } else {
                    $lines.RemoveAt($i)
                    $i--
                }
            }
        }
        if (-not $found) { $lines.Add("ALIVE_API_TOKEN=$token") }
        [IO.File]::WriteAllLines($path, $lines, $utf8)
    }

    function Set-PrivateAcl([string]$path) {
        if ($env:OS -ne 'Windows_NT') {
            if (Get-Command chmod -ErrorAction SilentlyContinue) { & chmod 600 $path }
            return
        }
        $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
        & icacls $path /inheritance:r /grant:r "*${sid}:(F)" | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Could not secure $path" }
        # Remove broad explicit grants if the host's default DACL carried them.
        foreach ($broad in @(
            'S-1-1-0',      # Everyone
            'S-1-5-4',      # Interactive
            'S-1-5-7',      # Anonymous
            'S-1-5-11',     # Authenticated Users
            'S-1-5-32-545', # Users
            'S-1-5-32-546'  # Guests
        )) {
            & icacls $path /remove:g "*$broad" 2>$null | Out-Null
        }
        & icacls $path /grant:r "*${sid}:(F)" | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Could not secure $path" }
    }

    function New-Token {
        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        try {
            $bytes = New-Object byte[] 32
            $rng.GetBytes($bytes)
        } finally {
            $rng.Dispose()
        }
        return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
    }

    if (-not (Test-Path -LiteralPath $envPath)) {
        if (-not (Test-Path -LiteralPath $examplePath)) {
            throw ".env.example is missing; cannot create .env"
        }
        Copy-Item -LiteralPath $examplePath -Destination $envPath
        if (-not $Quiet) { Write-Host 'Created .env from .env.example' }
    }

    $envToken = Get-EnvToken $envPath
    $fileToken = $null
    if (Test-Path -LiteralPath $tokenPath) {
        $fileToken = ([IO.File]::ReadAllText($tokenPath)).TrimEnd("`r", "`n")
    }

    $source = $null
    if (-not $Rotate -and (Test-Token $envToken) -and -not (Test-Placeholder $envToken)) {
        $token = $envToken
        $source = '.env'
    } elseif (-not $Rotate -and (Test-Token $fileToken) -and -not (Test-Placeholder $fileToken)) {
        $token = $fileToken
        $source = '.alive/token'
    } else {
        $token = New-Token
        $source = 'generated'
    }
    if (-not (Test-Token $token)) {
        throw 'Refusing to use an invalid local API token'
    }
    if ($envToken -and $fileToken -and $envToken -cne $fileToken -and -not $Quiet) {
        Write-Warning 'Synced .alive/token to the ALIVE_API_TOKEN already configured in .env.'
    }

    if (-not (Test-Path -LiteralPath $stateDir)) {
        New-Item -ItemType Directory -Path $stateDir | Out-Null
    }
    Set-EnvToken $envPath $token
    [IO.File]::WriteAllText($tokenPath, $token, $utf8)
    Set-PrivateAcl $envPath
    Set-PrivateAcl $tokenPath

    $clipboard = $false
    if (-not $NoClipboard) {
        try {
            Set-Clipboard -Value $token
            $clipboard = $true
        } catch {
            $clipboard = $false
        }
    }

    if (-not $Quiet) {
        Write-Host "Token ready ($source)."
        Write-Host "  .env:        $envPath"
        Write-Host "  local token: $tokenPath"
        if ($clipboard) {
            Write-Host '  Copied to the clipboard; paste it once into the dashboard or extension.'
        } else {
            Write-Host '  Clipboard unavailable; read the token from .env or .alive/token once.'
        }
        Write-Host 'Docker demo: run this script in the same checkout as compose, then docker compose up --build.'
        Write-Host 'Local demo:  ./scripts/dev.ps1'
        Write-Host 'Tokens are per checkout; keep this script and the running app in the same checkout.'
        Write-Host 'Restart a running app, or recreate a running compose stack, to apply a changed token.'
    }
} finally {
    Pop-Location
}
