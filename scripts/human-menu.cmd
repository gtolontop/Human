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
echo 5. Server status
echo 6. Stop server
echo 7. Rebuild private dataset pipeline
echo 8. Social simulation
echo 9. Eval mock
echo 10. Eval Qwen
echo 11. Open reports
echo 12. Open DiscordChatExporter
echo 13. Probe chat quality
echo 14. Show current activity
echo 0. Quit
echo.
set /p choice="Choice: "
if "%choice%"=="1" call scripts\chat-full.cmd
if "%choice%"=="2" call scripts\chat-mock.cmd
if "%choice%"=="3" call scripts\server-start-fast.cmd
if "%choice%"=="4" call scripts\server-start-quality.cmd
if "%choice%"=="5" call scripts\server-status.cmd
if "%choice%"=="6" call scripts\server-stop.cmd
if "%choice%"=="7" call scripts\pipeline-rebuild-all.cmd
if "%choice%"=="8" call scripts\social-sim.cmd
if "%choice%"=="9" call scripts\eval-mock.cmd
if "%choice%"=="10" call scripts\eval-qwen.cmd
if "%choice%"=="11" call scripts\open-reports.cmd
if "%choice%"=="12" call scripts\discord-exporter.cmd
if "%choice%"=="13" call scripts\probe-chat.cmd
if "%choice%"=="14" call scripts\activity-now.cmd
if "%choice%"=="0" exit /b 0
goto menu
