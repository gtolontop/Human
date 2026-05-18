@echo off
setlocal
cd /d "%~dp0\.."
echo === llama-server MTP support ===
powershell -NoProfile -Command "$server = 'C:\Users\teamr\Desktop\ai\llama-mtp\llama-server.exe'; if (!(Test-Path $server)) { $server = 'C:\Users\teamr\Desktop\ai\llama\llama-server.exe' }; $h = & $server --help 2>&1 | Out-String; Write-Output ('server=' + $server); if ($h -match 'draft-mtp') { Write-Output 'OK: draft-mtp supported' } else { Write-Output 'NO: this llama-server does not support draft-mtp yet'; Write-Output 'Run scripts\install-llama-mtp.cmd, then retry scripts\server-start-mtp.cmd' }"
pause
