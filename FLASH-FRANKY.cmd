@echo off
cd /d "%~dp0"
echo This replaces your robot firmware. Read docs\FIRMWARE.md and keep a private backup first.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\flash-wizard.ps1"
if errorlevel 1 echo Upload failed. Read the message above.
pause
