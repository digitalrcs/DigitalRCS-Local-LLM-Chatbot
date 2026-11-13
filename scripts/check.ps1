$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $root
$python = Join-Path $root '.venv/Scripts/python.exe'
if (Test-Path (Join-Path $root '.runtime/python.exe')) { $python = Join-Path $root '.runtime/python.exe' }
if (-not (Test-Path -LiteralPath $python)) { throw 'Run START-HERE.cmd first.' }
try {
    $health = Invoke-RestMethod 'http://127.0.0.1:8766/health' -TimeoutSec 3
    Write-Host ('Bridge status: ' + $health.status)
}
catch { Write-Host 'Bridge is not responding. Start START-FRANKY.cmd and retry.'; exit 1 }
try {
    $ready = Invoke-RestMethod 'http://127.0.0.1:8766/ready' -TimeoutSec 3
    foreach ($name in @('recognition', 'voice', 'chat')) {
        $check = $ready.checks.$name
        Write-Host ($name + ' [' + $check.status + ']: ' + $check.message)
    }
    if ($ready.status -eq 'starting') { Write-Host 'Still preparing. Leave the bridge open and check the dashboard shortly.' }
    if ($ready.status -eq 'degraded') { Write-Host 'One or more checks need attention. Follow the messages above.' }
}
catch { Write-Host 'Readiness details are unavailable. Restart the bridge to load the updated dashboard.' }
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | ForEach-Object { Write-Host ('Possible robot bridge address: http://' + $_.IPAddress + ':8766') }
Write-Host 'This checks connections, not audio quality or a complete conversation.'
