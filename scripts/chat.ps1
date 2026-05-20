$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
& (Join-Path $PSScriptRoot "start_qwen36_server.ps1")
python -m src.cli --chat --base-url "http://127.0.0.1:8080/v1" --api-key "yourbot-local" --model "qwen3.6-27b" --no-response-format @args
