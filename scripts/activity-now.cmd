@echo off
setlocal
cd /d "%~dp0\.."
python scripts\activity_now.py %*
