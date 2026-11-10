$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $root
$python = Join-Path $root '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run START-HERE.cmd first.' }
& $python bridge/configure.py
if ($LASTEXITCODE) { throw 'Provider setup was not completed.' }
