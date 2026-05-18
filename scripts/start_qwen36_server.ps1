param(
  [string]$ModelPath = "C:\Users\teamr\Desktop\ai\llama\models\Qwen3.6-27B-UD-IQ2_XXS.gguf",
  [string]$Quant = "",
  [string]$Alias = "qwen3.6-27b",
  [int]$Port = 8080,
  [int]$ContextSize = 32768,
  [string]$ApiKey = "yourbot-local"
)

$ErrorActionPreference = "Stop"
$Repo = Join-Path $PSScriptRoot ".."
$LlamaDir = "C:\Users\teamr\Desktop\ai\llama"
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
  throw "llama-server not found: $Server"
}
if (-not (Test-Path $ModelPath)) {
  throw "Qwen3.6 GGUF not found: $ModelPath"
}

try {
  Invoke-RestMethod -Uri "http://127.0.0.1:$Port/v1/models" -Headers @{ Authorization = "Bearer $ApiKey" } -TimeoutSec 2 | Out-Null
  exit 0
} catch {
  Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Args = @(
  "-m", $ModelPath,
  "-ngl", "99",
  "--flash-attn", "on",
  "-c", "$ContextSize",
  "--rope-scaling", "yarn",
  "--yarn-orig-ctx", "32768",
  "-ctk", "q4_0",
  "-ctv", "q4_0",
  "--parallel", "1",
  "--no-cont-batching",
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
