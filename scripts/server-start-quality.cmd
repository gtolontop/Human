@echo off
setlocal
cd /d "%~dp0\.."
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_qwen36_server.ps1 -Quant iq2_m
echo.
echo Qwen3.6 quality server ready on http://127.0.0.1:8080/v1
pause

