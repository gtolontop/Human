@echo off
setlocal
cd /d "%~dp0\.."
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_llama_server.ps1
python -m src.cli --chat --base-url http://127.0.0.1:8000/v1 --model llama3.2:1b --no-response-format %*
