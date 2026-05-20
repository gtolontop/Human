@echo off
setlocal
cd /d "%~dp0\.."
title Human - Qwen3.6 MTP Social Chat
echo ============================================
echo   HUMAN SOCIAL CHAT - Qwen3.6 MTP
echo ============================================
echo.
echo Modele : unsloth/Qwen3.6-27B-MTP-GGUF:UD-Q4_K_XL
echo Note   : requires llama.cpp with --spec-type draft-mtp
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_qwen36_server.ps1 -Mtp -ContextSize 8192 -Alias qwen3.6-27b-mtp -LlamaDir "C:\Users\teamr\Desktop\ai\llama-mtp"
if errorlevel 1 exit /b %errorlevel%
python -m src.cli --chat --base-url http://127.0.0.1:8080/v1 --api-key yourbot-local --model qwen3.6-27b-mtp --no-response-format --temperature 0.55 --max-tokens 160 --user-id local_user --display-name USER --conversation-id local_dm %*
