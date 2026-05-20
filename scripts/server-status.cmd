@echo off
setlocal
cd /d "%~dp0\.."
echo === llama-server process ===
powershell -NoProfile -Command "Get-Process llama-server -ErrorAction SilentlyContinue | Select-Object ProcessName,Id,CPU,Path | Format-Table -AutoSize"
echo.
echo === API models ===
powershell -NoProfile -Command "try { Invoke-RestMethod -Uri 'http://127.0.0.1:8080/v1/models' -Headers @{Authorization='Bearer yourbot-local'} -TimeoutSec 3 | ConvertTo-Json -Depth 4 } catch { Write-Output $_.Exception.Message }"
echo.
echo === GPU ===
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader
pause

