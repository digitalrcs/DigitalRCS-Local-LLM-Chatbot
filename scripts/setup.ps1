param([string]$Python)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $root
$venv = Join-Path $root '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $venv)) {
    if ($Python) {
        & $Python -c "import sys; assert (3,11) <= sys.version_info[:2] <= (3,13), 'Use Python 3.11 to 3.13'"
        if ($LASTEXITCODE) { throw 'Unsupported Python version.' }
        & $Python -m venv .venv
    } else {
        $found = $false
        foreach ($version in @('-3.13', '-3.12', '-3.11')) {
            if (Get-Command py -ErrorAction SilentlyContinue) {
                & py $version -c "import sys; assert sys.maxsize > 2**32" 2>$null
                if ($LASTEXITCODE -eq 0) { & py $version -m venv .venv; $found = $true; break }
            }
        }
        if (-not $found) { throw 'Install 64-bit Python 3.13 from python.org, then run START-HERE again. See docs/INSTALL.md.' }
    }
    if ($LASTEXITCODE) { throw 'Could not create the Python environment.' }
}
& $venv -m pip install -r bridge/requirements-lock.txt
if ($LASTEXITCODE) { throw 'Package installation failed. Check your Internet connection and try again.' }
& $venv bridge/configure.py
if ($LASTEXITCODE -eq 2) {
    Write-Host 'Setup cancelled. Existing settings were kept. Run START-HERE when you are ready to continue.'
    exit 2
}
if ($LASTEXITCODE) { throw 'Connection setup was not completed.' }
& $venv -c "import sys; sys.path.insert(0, 'bridge'); from settings import load_settings; assert load_settings()['model'], 'Choose a chat model before continuing'"
if ($LASTEXITCODE) { throw 'No usable provider configuration was saved. Run START-HERE again.' }
& $venv bridge/download_voice.py
if ($LASTEXITCODE) { throw 'Voice download failed. Run setup again to retry.' }
& $venv -c "import sys; sys.path.insert(0, 'bridge'); from server import recognizer, wake_recognizer; recognizer(); wake_recognizer(); print('English speech models ready')"
if ($LASTEXITCODE) { throw 'Speech recognition download failed. Run setup again to retry.' }
Write-Host 'Setup complete. Double-click START-FRANKY.cmd, then open http://localhost:8766.' -ForegroundColor Green
