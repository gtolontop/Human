@echo off
setlocal
cd /d "%~dp0\.."
python scripts\simulate_social.py --reset
pause

