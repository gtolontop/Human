@echo off
setlocal
cd /d "%~dp0\.."
echo Rebuilding local private pipeline...
python scripts\ingest_discord.py --input data/raw --output data/processed/ingested.jsonl
python scripts\anonymize.py --input data/processed/ingested.jsonl --output data/processed/anonymized.jsonl --summary data/processed/anonymization_summary.json --target-author-id 746700907248484393
python scripts\build_cleaned_conversations.py --input data/raw --output data/processed/conversations.cleaned.jsonl --target-user-id 746700907248484393
python scripts\build_style_profile.py --input data/processed/anonymized.jsonl --output data/processed/style_profile.json
python scripts\build_fewshot_examples.py --input data/processed/conversations.cleaned.jsonl --output data/processed/fewshot_examples.json --limit 12
python scripts\build_eval_split.py --input data/processed/conversations.cleaned.jsonl --output data/processed/eval.jsonl --limit 100
echo.
echo Done. Private outputs stayed in data\processed.
pause

