# Build an OFFLINE bundle on Windows for PCs that cannot download Python or packages (intranet; user request 2026-10-17).
#   powershell -ExecutionPolicy Bypass -File scripts\build-offline-bundle.ps1                # base backend
#   ... -Qwen            # + PyTorch (CPU), Qwen3-TTS, faster-whisper
#   ... -Qwen -Cuda      # + PyTorch cu128 for NVIDIA GPUs (≈ 3 GB; too big for a GitHub release asset — carry it on a USB stick)
#   ... -Models          # + the model weights (≈ 5 GB)
#   ... -Data            # + this PC's registered voices and noise clips (%APPDATA%\NursingTTS; private, never in a release)
# Output: <Out>\nursing-tts-offline-win-x64[-qwen][-cuda][-models].zip  (python\, models\hub\, bundle.json)
param([switch]$Qwen, [switch]$Cuda, [switch]$Models, [switch]$Data, [string]$Out = "dist-offline")
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$PbsTag = "20261013"
$PyVer = "3.12.15"
$Triple = "x86_64-pc-windows-msvc"
$Name = "nursing-tts-offline-win-x64" + $(if ($Qwen) { "-qwen" } else { "" }) + $(if ($Cuda) { "-cuda" } else { "" }) + $(if ($Models) { "-models" } else { "" }) + $(if ($Data) { "-data" } else { "" })
$Work = Join-Path $Out $Name
if (Test-Path $Work) { Remove-Item -Recurse -Force $Work }
New-Item -ItemType Directory -Force -Path $Work, (Join-Path $Out "cache") | Out-Null

Write-Host "== 1/4 Python $PyVer ($Triple)"
$Tarball = "cpython-$PyVer+$PbsTag-$Triple-install_only.tar.gz"
$TarPath = Join-Path $Out "cache\$Tarball"
if (-not (Test-Path $TarPath)) {
  Invoke-WebRequest -Uri "https://github.com/astral-sh/python-build-standalone/releases/download/$PbsTag/$Tarball" -OutFile $TarPath
}
tar -xzf $TarPath -C $Work
$Py = Join-Path $Work "python\python.exe"
& $Py --version

Write-Host "== 2/4 packages"
& $Py -m pip install --upgrade pip --quiet
& $Py -m pip install --no-warn-script-location -r backend\requirements.txt
if ($Qwen) {
  if ($Cuda) { & $Py -m pip install --no-warn-script-location torch torchaudio --index-url https://download.pytorch.org/whl/cu128 }
  else { & $Py -m pip install --no-warn-script-location torch torchaudio }
  & $Py -m pip install --no-warn-script-location -r backend\requirements-qwen.txt
}
& $Py -c "import fastapi, uvicorn, numpy, scipy, soundfile, httpx, openpyxl; print('backend imports ok')"
if ($Qwen) { & $Py -c "import torch, qwen_tts, faster_whisper; print('qwen imports ok, torch', torch.__version__)" }
Get-ChildItem -Path (Join-Path $Work "python") -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

if ($Models) {
  Write-Host "== 3/4 models (Hugging Face -> models\hub)"
  New-Item -ItemType Directory -Force -Path (Join-Path $Work "models\hub") | Out-Null
  $env:HF_HUB_CACHE = (Join-Path $Work "models\hub")
  & $Py -c "from huggingface_hub import snapshot_download as d; d('Qwen/Qwen3-TTS-12Hz-1.7B-Base'); d('Systran/faster-whisper-small'); print('models ok')"
  Remove-Item Env:HF_HUB_CACHE
} else { Write-Host "== 3/4 models skipped" }

if ($Data) {
  $DataDir = if ($env:NURSING_TTS_DATA) { $env:NURSING_TTS_DATA } else { Join-Path $env:APPDATA "NursingTTS" }
  Write-Host "== 3b/4 voices + noises from $DataDir"
  New-Item -ItemType Directory -Force -Path (Join-Path $Work "data") | Out-Null
  foreach ($sub in @("voices", "noises")) {
    $src = Join-Path $DataDir $sub
    if (Test-Path $src) { Copy-Item -Recurse -Force $src (Join-Path $Work "data\$sub") }
  }
}

Write-Host "== 4/4 bundle.json + zip"
$AppVersion = ""
try { $AppVersion = (Get-Content app\package.json | ConvertFrom-Json).version } catch {}
$meta = @{ name = "nursing-tts-offline"; platform = "win"; arch = "x64"; python = $PyVer; qwen = [bool]$Qwen; cuda = [bool]$Cuda; models = [bool]$Models; data = [bool]$Data; app_version = $AppVersion; created = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") }
$meta | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $Work "bundle.json")
$Zip = Join-Path $Out "$Name.zip"
if (Test-Path $Zip) { Remove-Item $Zip }
Compress-Archive -Path $Work -DestinationPath $Zip -CompressionLevel Optimal
Write-Host "done: $Zip ($([math]::Round((Get-Item $Zip).Length / 1MB)) MB)"
