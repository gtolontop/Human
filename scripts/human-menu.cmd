@echo off
setlocal
cd /d "%~dp0\.."
:menu
cls
echo ============================================
echo              HUMAN CONTROL PANEL
echo ============================================
echo.
echo 1. Chat complet Qwen3.6 social
echo 2. Chat mock offline
echo 3. Start Qwen3.6 fast server IQ2_XXS
echo 4. Start Qwen3.6 quality server IQ2_M
echo 5. Start Qwen3.6 MTP server
echo 6. Chat complet Qwen3.6 MTP
echo 7. Check MTP support
echo 8. Install/update llama.cpp MTP
echo 9. Server status
echo 10. Stop server
echo 11. Rebuild private dataset pipeline
echo 12. Social simulation
echo 13. Eval mock
echo 14. Eval Qwen
echo 15. Open reports
echo 16. Open DiscordChatExporter
echo 17. Probe chat quality
echo 18. Show current activity
echo 0. Quit
echo.
set /p choice="Choice: "
if "%choice%"=="1" call scripts\chat-full.cmd
if "%choice%"=="2" call scripts\chat-mock.cmd
if "%choice%"=="3" call scripts\server-start-fast.cmd
if "%choice%"=="4" call scripts\server-start-quality.cmd
if "%choice%"=="5" call scripts\server-start-mtp.cmd
if "%choice%"=="6" call scripts\chat-mtp.cmd
if "%choice%"=="7" call scripts\server-check-mtp.cmd
if "%choice%"=="8" call scripts\install-llama-mtp.cmd
if "%choice%"=="9" call scripts\server-status.cmd
if "%choice%"=="10" call scripts\server-stop.cmd
if "%choice%"=="11" call scripts\pipeline-rebuild-all.cmd
if "%choice%"=="12" call scripts\social-sim.cmd
if "%choice%"=="13" call scripts\eval-mock.cmd
if "%choice%"=="14" call scripts\eval-qwen.cmd
if "%choice%"=="15" call scripts\open-reports.cmd
if "%choice%"=="16" call scripts\discord-exporter.cmd
if "%choice%"=="17" call scripts\probe-chat.cmd
if "%choice%"=="18" call scripts\activity-now.cmd
if "%choice%"=="0" exit /b 0
goto menu
