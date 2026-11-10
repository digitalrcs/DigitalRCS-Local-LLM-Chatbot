@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\check.ps1"
if errorlevel 1 echo Something needs attention. Read the message above.
pause
