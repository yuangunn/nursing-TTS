# One-time backend setup for Windows (PowerShell).
#   .\scripts\setup-backend.ps1          # base install
#   .\scripts\setup-backend.ps1 -Qwen    # also install Qwen3-TTS (needs NVIDIA GPU + CUDA PyTorch)
param([switch]$Qwen)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\backend")

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if (-not $py) { Write-Error "Python 3.10+ not found. Install from https://www.python.org/downloads/ (check 'Add to PATH')." }

if (-not (Test-Path ".venv")) { & $py.Source -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\pip.exe install -r requirements.txt

if ($Qwen) {
  Write-Host "Installing PyTorch with CUDA and Qwen3-TTS (several GB)..."
  & .\.venv\Scripts\pip.exe install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
  & .\.venv\Scripts\pip.exe install -r requirements-qwen.txt
}

Write-Host ""
Write-Host "Backend ready. Start the app with:  cd app; npm install; npm run dev"
