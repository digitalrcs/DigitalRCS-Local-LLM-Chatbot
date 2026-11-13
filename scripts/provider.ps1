$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $root
$python = Join-Path $root '.venv/Scripts/python.exe'
if (Test-Path (Join-Path $root '.runtime/python.exe')) { $python = Join-Path $root '.runtime/python.exe' }
if (-not (Test-Path -LiteralPath $python)) { throw 'Run START-HERE.cmd first.' }
& $python bridge/configure.py
if ($LASTEXITCODE -eq 2) { Write-Host 'Provider change cancelled. Existing settings were kept.'; exit 2 }
if ($LASTEXITCODE) { throw 'Provider setup was not completed.' }
