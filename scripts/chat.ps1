$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
python -m src.cli --chat --base-url "http://127.0.0.1:8000/v1" --model "Qwen/Qwen3.6-27B" @args

