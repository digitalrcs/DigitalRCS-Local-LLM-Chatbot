@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build-firmware.ps1" -Install
if errorlevel 1 echo Build failed. Read the message above.
pause
