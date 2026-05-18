@echo off
setlocal
cd /d "%~dp0\.."
title Human - Mock Chat
python -m src.cli --chat --mock --user-id local_user --display-name USER --conversation-id local_dm %*

