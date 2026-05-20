@echo off
setlocal
echo Stopping llama-server...
taskkill /F /IM llama-server.exe >nul 2>&1
if errorlevel 1 (
  echo No llama-server process found.
) else (
  echo Stopped.
)
pause

