@echo off
setlocal
cd /d "%~dp0\.."
if exist reports\eval_style.md start "" reports\eval_style.md
if exist reports start "" reports
if not exist reports echo No reports folder yet.
pause

