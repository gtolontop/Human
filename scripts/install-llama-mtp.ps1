param(
  [string]$InstallDir = "C:\Users\teamr\Desktop\ai\llama-mtp",
  [string]$SourceDllDir = "C:\Users\teamr\Desktop\ai\llama"
)

$ErrorActionPreference = "Stop"
$Repo = Join-Path $PSScriptRoot ".."
$DownloadDir = Join-Path $Repo ".tools\downloads"
New-Item -ItemType Directory -Force -Path $DownloadDir | Out-Null
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

$Release = Invoke-RestMethod -Uri "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest" -Headers @{ "User-Agent" = "HumanStyleCLI" }
$Asset = $Release.assets |
  Where-Object { $_.name -match "^llama-.*-bin-win-cuda-.*x64\.zip$" -and $_.name -notmatch "cudart" } |
  Select-Object -First 1

if (-not $Asset) {
  throw "Could not find a Windows CUDA x64 llama.cpp asset in latest release $($Release.tag_name)."
}

$ZipPath = Join-Path $DownloadDir $Asset.name
Write-Output "Downloading $($Asset.name) from llama.cpp $($Release.tag_name)..."
Invoke-WebRequest -Uri $Asset.browser_download_url -OutFile $ZipPath

$ExtractDir = Join-Path $DownloadDir ("llama-" + $Release.tag_name)
if (Test-Path $ExtractDir) {
  Remove-Item -Recurse -Force -LiteralPath $ExtractDir
}
New-Item -ItemType Directory -Force -Path $ExtractDir | Out-Null
Expand-Archive -LiteralPath $ZipPath -DestinationPath $ExtractDir -Force

$Server = Get-ChildItem -Path $ExtractDir -Recurse -Filter "llama-server.exe" | Select-Object -First 1
if (-not $Server) {
  throw "Downloaded archive did not contain llama-server.exe"
}

Copy-Item -Path (Join-Path $Server.DirectoryName "*") -Destination $InstallDir -Recurse -Force
if (Test-Path $SourceDllDir) {
  Copy-Item -Path (Join-Path $SourceDllDir "*.dll") -Destination $InstallDir -Force -ErrorAction SilentlyContinue
}

$HelpText = (& (Join-Path $InstallDir "llama-server.exe") --help 2>&1 | ForEach-Object { "$_" } | Out-String)
if ($HelpText -match "draft-mtp") {
  Write-Output "OK: installed llama.cpp with draft-mtp support at $InstallDir"
  exit 0
}

Write-Output "Installed latest llama.cpp at $InstallDir, but draft-mtp was not found in --help."
Write-Output "Try again after llama.cpp publishes a build containing Qwen3.6 MTP support."
exit 2
