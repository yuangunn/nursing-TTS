#!/usr/bin/env bash
# Build an OFFLINE bundle for PCs that cannot download Python or packages (intranet; user request 2026-10-17).
#
#   scripts/build-offline-bundle.sh                 # base backend (pipeline + system/HTTP engines)
#   scripts/build-offline-bundle.sh --qwen          # + PyTorch, Qwen3-TTS, faster-whisper (voice cloning)
#   scripts/build-offline-bundle.sh --qwen --models # + the model weights (Qwen 1.7B ≈ 4.5 GB, whisper small ≈ 0.5 GB)
#   scripts/build-offline-bundle.sh --data          # + this PC's registered voices and noise clips (app data folder)
#   scripts/build-offline-bundle.sh --out DIR       # where to build (default: dist-offline/; relative paths are from the repo root)
#   scripts/build-offline-bundle.sh --no-zip        # leave the folder only (CI puts it straight into the -offline installer)
#
# Output: <out>/nursing-tts-offline-<os>-<arch>[-qwen][-models].zip containing
#   python/      relocatable CPython (python-build-standalone) with every package installed
#   models/hub/  Hugging Face cache (only with --models)
#   data/        voices/ and noises/ copied from this PC's app data folder (only with --data; private, never in a release)
#   bundle.json  what is inside
# On the intranet PC: install the app, then 설정 → 백엔드 → "📦 오프라인 번들 가져오기" (or 처음 설정 마법사) and pick the zip.
# Models can also be copied later into the folder shown under 설정 → 로컬 모델.
set -euo pipefail
cd "$(dirname "$0")/.."

PBS_TAG="20261013"          # astral-sh/python-build-standalone release
PY_VER="3.12.15"
OUT="dist-offline"
WITH_QWEN=0
WITH_MODELS=0
WITH_DATA=0
NO_ZIP=0
for a in "$@"; do
  case "$a" in
    --qwen) WITH_QWEN=1 ;;
    --models) WITH_MODELS=1 ;;
    --data) WITH_DATA=1 ;;
    --no-zip) NO_ZIP=1 ;;
    --out=*) OUT="${a#--out=}" ;;
    --out) shift_out=1 ;;
    *) if [ "${shift_out:-0}" = 1 ]; then OUT="$a"; shift_out=0; else echo "unknown option $a" >&2; exit 2; fi ;;
  esac
done

case "$(uname -s)-$(uname -m)" in
  Darwin-arm64) TRIPLE="aarch64-apple-darwin"; OS="mac"; ARCH="arm64" ;;
  Darwin-x86_64) TRIPLE="x86_64-apple-darwin"; OS="mac"; ARCH="x64" ;;
  Linux-x86_64) TRIPLE="x86_64-unknown-linux-gnu"; OS="linux"; ARCH="x64" ;;
  *) echo "unsupported platform $(uname -s)-$(uname -m) (use build-offline-bundle.ps1 on Windows)" >&2; exit 2 ;;
esac
SUFFIX=""
if [ $WITH_QWEN = 1 ]; then SUFFIX="$SUFFIX-qwen"; fi
if [ $WITH_MODELS = 1 ]; then SUFFIX="$SUFFIX-models"; fi
if [ $WITH_DATA = 1 ]; then SUFFIX="$SUFFIX-data"; fi
NAME="nursing-tts-offline-${OS}-${ARCH}${SUFFIX}"
WORK="$OUT/$NAME"
rm -rf "$WORK"; mkdir -p "$WORK"

echo "== 1/4 Python ${PY_VER} (${TRIPLE})"
TARBALL="cpython-${PY_VER}+${PBS_TAG}-${TRIPLE}-install_only.tar.gz"
mkdir -p "$OUT/cache"
if [ ! -f "$OUT/cache/$TARBALL" ]; then
  curl -L --fail -o "$OUT/cache/$TARBALL" "https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_TAG}/${TARBALL}"
fi
tar -xzf "$OUT/cache/$TARBALL" -C "$WORK"          # creates $WORK/python
PY="$WORK/python/bin/python3"
"$PY" --version

echo "== 2/4 packages"
"$PY" -m pip install --upgrade pip --quiet
"$PY" -m pip install --no-warn-script-location -r backend/requirements.txt
if [ $WITH_QWEN = 1 ]; then
  "$PY" -m pip install --no-warn-script-location torch torchaudio
  "$PY" -m pip install --no-warn-script-location -r backend/requirements-qwen.txt
fi
# the bundle runs the backend from the app's resources folder, so only the imports matter
"$PY" -c "import fastapi, uvicorn, numpy, scipy, soundfile, httpx, openpyxl; print('backend imports ok')"
if [ $WITH_QWEN = 1 ]; then "$PY" -c "import torch, qwen_tts, faster_whisper; print('qwen imports ok, torch', torch.__version__)"; fi
find "$WORK/python" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true

if [ $WITH_MODELS = 1 ]; then
  echo "== 3/4 models (Hugging Face → models/hub)"
  mkdir -p "$WORK/models/hub"
  HF_HUB_CACHE="$WORK/models/hub" "$PY" -c "from huggingface_hub import snapshot_download as d; d('Qwen/Qwen3-TTS-12Hz-1.7B-Base'); d('Systran/faster-whisper-small'); print('models ok')"
else
  echo "== 3/4 models skipped (copy them later into the folder shown under 설정 → 로컬 모델)"
fi

if [ $WITH_DATA = 1 ]; then
  # same folder the backend uses (config.py data_dir): NURSING_TTS_DATA or the OS app-data folder
  DATA_DIR="${NURSING_TTS_DATA:-}"
  if [ -z "$DATA_DIR" ]; then
    case "$OS" in mac) DATA_DIR="$HOME/Library/Application Support/NursingTTS" ;; *) DATA_DIR="$HOME/.nursing-tts" ;; esac
  fi
  echo "== 3b/4 voices + noises from $DATA_DIR"
  mkdir -p "$WORK/data"
  for sub in voices noises; do
    if [ -d "$DATA_DIR/$sub" ]; then cp -R "$DATA_DIR/$sub" "$WORK/data/$sub"; echo "   $sub: $(du -sh "$WORK/data/$sub" | cut -f1)"; fi
  done
fi

echo "== 4/4 bundle.json + zip"
APP_VERSION=$(node -p "require('./app/package.json').version" 2>/dev/null || echo "")
QWEN_JSON=false; MODELS_JSON=false; DATA_JSON=false
if [ $WITH_QWEN = 1 ]; then QWEN_JSON=true; fi
if [ $WITH_MODELS = 1 ]; then MODELS_JSON=true; fi
if [ $WITH_DATA = 1 ]; then DATA_JSON=true; fi
cat > "$WORK/bundle.json" <<EOF
{"name": "nursing-tts-offline", "platform": "${OS}", "arch": "${ARCH}", "python": "${PY_VER}", "qwen": ${QWEN_JSON},
 "models": ${MODELS_JSON}, "data": ${DATA_JSON}, "app_version": "${APP_VERSION}", "created": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
EOF
if [ $NO_ZIP = 1 ]; then echo "done: $WORK (no zip)"; exit 0; fi
rm -f "$OUT/$NAME.zip"
(cd "$OUT" && zip -ryq "$NAME.zip" "$NAME")
du -sh "$OUT/$NAME.zip"
echo "done: $OUT/$NAME.zip"
