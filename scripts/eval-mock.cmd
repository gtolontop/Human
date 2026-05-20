@echo off
setlocal
cd /d "%~dp0\.."
python scripts\run_style_eval.py --eval data/processed/eval.jsonl --mock --blind-review
pause

