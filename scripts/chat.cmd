@echo off
setlocal
cd /d "%~dp0\.."
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_qwen36_server.ps1 -ContextSize 8192
python -m src.cli --chat --base-url http://127.0.0.1:8080/v1 --api-key yourbot-local --model qwen3.6-27b --no-response-format --timeout 240 --max-tokens 96 %*
