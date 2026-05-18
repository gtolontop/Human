@echo off
setlocal
cd /d "%~dp0\.."
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_qwen36_server.ps1 -Quant iq2_xxs
python scripts\probe_chat_quality.py --base-url http://127.0.0.1:8080/v1 --api-key yourbot-local --model qwen3.6-27b %*
pause
