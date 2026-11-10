$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $root
$python = Join-Path $root '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run START-HERE.cmd first.' }
if (-not (Test-Path 'bridge/config.json')) { throw 'Run START-HERE.cmd to choose your LM Studio connection.' }
Write-Host 'Franky voice picker: http://localhost:8766'
Write-Host 'Keep this window open. Press Ctrl+C to stop.'
& $python -m uvicorn server:app --app-dir bridge --host 0.0.0.0 --port 8766
if ($LASTEXITCODE) { throw 'Bridge stopped with an error. See docs/TROUBLESHOOTING.md.' }
