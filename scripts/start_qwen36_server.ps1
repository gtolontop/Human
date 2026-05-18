param(
  [string]$ModelPath = "C:\Users\teamr\Desktop\ai\llama\models\Qwen3.6-27B-UD-IQ2_XXS.gguf",
  [string]$Quant = "",
  [string]$Alias = "qwen3.6-27b",
  [int]$Port = 8080,
  [int]$ContextSize = 32768,
  [string]$ApiKey = "yourbot-local",
  [switch]$Mtp,
  [string]$MtpRepo = "unsloth/Qwen3.6-27B-MTP-GGUF:UD-Q4_K_XL",
  [int]$MtpDraftN = 6,
  [switch]$Offline,
  [string]$LlamaDir = "C:\Users\teamr\Desktop\ai\llama"
)

$ErrorActionPreference = "Stop"
$Repo = Join-Path $PSScriptRoot ".."
$Server = Join-Path $LlamaDir "llama-server.exe"
$ModelsDir = Join-Path $LlamaDir "models"
$LogDir = Join-Path $Repo "logs"
$OutLog = Join-Path $LogDir "qwen36-server.out.log"
$ErrLog = Join-Path $LogDir "qwen36-server.err.log"

if ($Quant) {
  $Map = @{
    "iq2_xxs" = "Qwen3.6-27B-UD-IQ2_XXS.gguf"
    "iq2_m" = "Qwen3.6-27B-UD-IQ2_M.gguf"
    "q2_k_xl" = "Qwen3.6-27B-UD-Q2_K_XL.gguf"
    "q3_k_xl" = "Qwen3.6-27B-UD-Q3_K_XL.gguf"
  }
  $Key = $Quant.ToLowerInvariant()
  if (-not $Map.ContainsKey($Key)) {
    throw "Unknown quant '$Quant'. Use iq2_xxs, iq2_m, q2_k_xl, or q3_k_xl."
  }
  $ModelPath = Join-Path $ModelsDir $Map[$Key]
}

if (-not (Test-Path $Server)) {
  Write-Output "llama-server not found: $Server"
  if ($Mtp) {
    Write-Output "Run scripts\install-llama-mtp.cmd first, or pass -LlamaDir to a llama.cpp build with draft-mtp."
  }
  exit 2
}
if ((-not $Mtp) -and (-not (Test-Path $ModelPath))) {
  throw "Qwen3.6 GGUF not found: $ModelPath"
}
if ($Mtp) {
  $PreviousErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  $HelpText = (& $Server --help 2>&1 | ForEach-Object { "$_" } | Out-String)
  $ErrorActionPreference = $PreviousErrorActionPreference
  if ($HelpText -notmatch "draft-mtp") {
    Write-Output @"
This llama-server build does not support Qwen3.6 MTP yet.
Current server: $Server
Need llama.cpp with '--spec-type draft-mtp' support.
Docs: https://unsloth.ai/docs/models/qwen3.6#mtp-guide

For now use:
  scripts\server-start-fast.cmd
"@
    exit 3
  }
}

try {
  $Existing = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/v1/models" -Headers @{ Authorization = "Bearer $ApiKey" } -TimeoutSec 2
  $ExistingJson = $Existing | ConvertTo-Json -Depth 8
  if ($ExistingJson -match [regex]::Escape($Alias)) {
    exit 0
  }
  Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force
} catch {
  Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Args = @(
  "-ngl", "99",
  "--flash-attn", "on",
  "-c", "$ContextSize",
  "-ctk", "q4_0",
  "-ctv", "q4_0",
  "-np", "1",
  "-b", "1024",
  "-ub", "512",
  "--jinja",
  "--reasoning", "off",
  "--reasoning-budget", "0",
  "--temp", "0.6",
  "--top-k", "20",
  "--top-p", "0.95",
  "--min-p", "0.0",
  "--alias", $Alias,
  "--host", "127.0.0.1",
  "--port", "$Port",
  "--api-key", $ApiKey
)
if ($Mtp) {
  $env:LLAMA_CACHE = $MtpRepo.Split(":")[0]
  $Args = @("-hf", $MtpRepo) + $Args + @(
    "--spec-type", "draft-mtp",
    "--spec-draft-n-max", "$MtpDraftN"
  )
  if ($Offline) {
    $Args += "--offline"
  }
} else {
  $Args = @("-m", $ModelPath, "--rope-scaling", "yarn", "--yarn-orig-ctx", "32768") + $Args + @("--no-cont-batching")
}

$Process = Start-Process -FilePath $Server -WorkingDirectory $LlamaDir -ArgumentList $Args -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog -WindowStyle Hidden -PassThru
for ($i = 0; $i -lt 120; $i++) {
  Start-Sleep -Seconds 1
  try {
    Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 1 | Out-Null
    Write-Output "Qwen3.6 server ready pid=$($Process.Id) model=$Alias port=$Port"
    exit 0
  } catch {
    if ($Process.HasExited) {
      Get-Content $ErrLog -Tail 100 -ErrorAction SilentlyContinue
      throw "Qwen3.6 server exited with code $($Process.ExitCode)"
    }
  }
}

Get-Content $ErrLog -Tail 100 -ErrorAction SilentlyContinue
throw "Qwen3.6 server did not become ready on port $Port"
