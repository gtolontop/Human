param(
  [string]$ModelManifest = "registry.ollama.ai\library\llama3.2\1b",
  [string]$Alias = "llama3.2:1b",
  [int]$Port = 8000,
  [int]$ContextSize = 4096
)

$ErrorActionPreference = "Stop"
$Repo = Join-Path $PSScriptRoot ".."
$Server = Join-Path $env:USERPROFILE ".unsloth\llama.cpp\build\bin\Release\llama-server.exe"
$ManifestPath = Join-Path (Join-Path $env:USERPROFILE ".ollama\models\manifests") $ModelManifest
$LogDir = Join-Path $Repo "logs"
$OutLog = Join-Path $LogDir "llama-server.out.log"
$ErrLog = Join-Path $LogDir "llama-server.err.log"

if (-not (Test-Path $Server)) {
  throw "llama-server not found: $Server"
}
if (-not (Test-Path $ManifestPath)) {
  throw "Ollama manifest not found: $ManifestPath"
}

try {
  Invoke-RestMethod -Uri "http://127.0.0.1:$Port/v1/models" -TimeoutSec 2 | Out-Null
  exit 0
} catch {
  Get-Process llama-server -ErrorAction SilentlyContinue | Stop-Process -Force
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Manifest = Get-Content $ManifestPath | ConvertFrom-Json
$Layer = $Manifest.layers | Where-Object { $_.mediaType -eq "application/vnd.ollama.image.model" } | Select-Object -First 1
$Digest = $Layer.digest.Substring(7)
$Model = Join-Path (Join-Path $env:USERPROFILE ".ollama\models\blobs") "sha256-$Digest"

$Args = @(
  "-m", $Model,
  "--host", "127.0.0.1",
  "--port", "$Port",
  "--alias", $Alias,
  "-ngl", "auto",
  "-c", "$ContextSize",
  "-fa", "on"
)

$Process = Start-Process -FilePath $Server -ArgumentList $Args -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog -WindowStyle Hidden -PassThru
for ($i = 0; $i -lt 60; $i++) {
  Start-Sleep -Seconds 1
  try {
    Invoke-RestMethod -Uri "http://127.0.0.1:$Port/v1/models" -TimeoutSec 1 | Out-Null
    Write-Output "llama-server ready pid=$($Process.Id) model=$Alias port=$Port"
    exit 0
  } catch {
    if ($Process.HasExited) {
      Get-Content $ErrLog -Tail 80 -ErrorAction SilentlyContinue
      throw "llama-server exited with code $($Process.ExitCode)"
    }
  }
}

Get-Content $ErrLog -Tail 80 -ErrorAction SilentlyContinue
throw "llama-server did not become ready on port $Port"
