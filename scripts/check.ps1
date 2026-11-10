$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $root
$python = Join-Path $root '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run START-HERE.cmd first.' }
& $python -c "import sys; sys.path.insert(0, 'bridge'); from settings import load_settings; from configure import available_models; s=load_settings(); ids=available_models(s['lm_studio_url']); assert s['lm_studio_model'] in ids, 'Selected model not available'; print('LM Studio reachable; selected model listed.')"
if ($LASTEXITCODE) { throw 'LM Studio check failed. Start its server and load your chosen model.' }
try { $health = Invoke-RestMethod 'http://127.0.0.1:8766/health'; Write-Host ('Bridge status: ' + $health.status) }
catch { Write-Host 'Bridge is not responding. Start START-FRANKY.cmd and retry.'; exit 1 }
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | ForEach-Object { Write-Host ('Possible robot bridge address: http://' + $_.IPAddress + ':8766') }
Write-Host 'This checks connections, not audio quality or a complete conversation.'
