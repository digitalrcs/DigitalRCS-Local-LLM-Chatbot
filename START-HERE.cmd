@echo off
cd /d "%~dp0"
if exist "%~dp0FrankySetup.exe" (
    start "" "%~dp0FrankySetup.exe"
    exit /b
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1"
if errorlevel 1 echo Something needs attention. Read the message above.
pause
