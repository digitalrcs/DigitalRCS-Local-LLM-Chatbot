$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $root
$python = Join-Path $root '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run START-HERE.cmd first.' }
& $python bridge/host_config.py
if ($LASTEXITCODE -eq 2) { Write-Host 'Address change cancelled.'; exit 2 }
if ($LASTEXITCODE) { throw 'Bridge address was not changed. Read the message above.' }
