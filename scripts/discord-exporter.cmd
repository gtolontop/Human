@echo off
setlocal
cd /d "%~dp0\.."
set "EXPORTER=.tools\DiscordChatExporter\2.47.1\gui\DiscordChatExporter.exe"
if not exist "%EXPORTER%" (
  echo DiscordChatExporter GUI not found:
  echo %CD%\%EXPORTER%
  exit /b 1
)
start "" "%EXPORTER%"
echo Exporter opened.
echo Save JSON exports into: %CD%\data\raw
