@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\provider.ps1"
if errorlevel 1 echo Read the message above before closing.
pause
