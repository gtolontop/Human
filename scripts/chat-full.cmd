@echo off
setlocal
cd /d "%~dp0\.."
title Human - Qwen3.6 Social Chat
echo ============================================
echo   HUMAN SOCIAL CHAT - Qwen3.6 quant local
echo ============================================
echo.
echo Modele : Qwen3.6-27B IQ2_XXS
echo Etat  : state\social_state.json
echo Tips  : /reset pour vider la session, /exit pour quitter
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_qwen36_server.ps1 -Quant iq2_xxs
python -m src.cli --chat --base-url http://127.0.0.1:8080/v1 --api-key yourbot-local --model qwen3.6-27b --no-response-format --user-id local_user --display-name USER --conversation-id local_dm %*

