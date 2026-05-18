@echo off
setlocal
cd /d "%~dp0\.."
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_qwen36_server.ps1 -Mtp -ContextSize 8192 -Alias qwen3.6-27b-mtp -LlamaDir "C:\Users\teamr\Desktop\ai\llama-mtp"
if errorlevel 1 exit /b %errorlevel%
echo.
echo Qwen3.6 MTP server ready on http://127.0.0.1:8080/v1
pause
