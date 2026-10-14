#!/usr/bin/env bash
# One-time backend setup for macOS / Linux.
#   ./scripts/setup-backend.sh          # base install (pipeline + system/HTTP engines)
#   ./scripts/setup-backend.sh --qwen   # also install Qwen3-TTS (built-in Korean voice cloning, needs GPU/MPS)
set -euo pipefail
cd "$(dirname "$0")/../backend"

PY=${PYTHON:-python3}
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "python3 not found. Install Python 3.10+ (https://www.python.org/downloads/)" >&2
  exit 1
fi

if [ ! -d .venv ]; then
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

if [ "${1:-}" = "--qwen" ]; then
  echo "Installing Qwen3-TTS + faster-whisper (this downloads PyTorch; several GB)..."
  pip install -r requirements-qwen.txt
fi

echo
echo "Backend ready. Start the app with:  cd app && npm install && npm run dev"
