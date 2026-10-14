"""Qwen3-TTS wrapper (Korean supported, Apache-2.0, zero-shot cloning from ~3 s).

Setup (separate venv recommended; needs an NVIDIA GPU, or CPU/MPS with dtype=float32):
    pip install -U qwen-tts fastapi uvicorn python-multipart soundfile
    python scripts/servers/qwen3_tts_server.py --port 8081
App settings → 커스텀 HTTP TTS 서버 URL: http://127.0.0.1:8081/synthesize

API per the official model card (https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base):
    model = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-0.6B-Base", device_map="cuda:0", dtype=torch.bfloat16)
    wavs, sr = model.generate_voice_clone(text=..., language="Korean", ref_audio=path, ref_text=...)
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from _common import make_app, run  # noqa: E402

MODEL_ID = os.environ.get("QWEN_TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-0.6B-Base")
_model = None
_lock = threading.Lock()


def _load():
    global _model
    if _model is None:
        import torch
        from qwen_tts import Qwen3TTSModel

        if torch.cuda.is_available():
            kwargs = {"device_map": "cuda:0", "dtype": torch.bfloat16}
        elif torch.backends.mps.is_available():  # Apple Silicon: bf16 works, RTF ~1.9 on M4 for the 0.6B model
            kwargs = {"device_map": "mps", "dtype": torch.bfloat16}
        else:
            kwargs = {"device_map": "cpu", "dtype": torch.float32}
        _model = Qwen3TTSModel.from_pretrained(MODEL_ID, **kwargs)
    return _model


def synthesize(text: str, ref_audio: Path | None, ref_text: str, seed: int | None):
    if ref_audio is None:
        raise RuntimeError("ref_audio is required for voice cloning")
    model = _load()
    with _lock:
        if seed is not None:
            import torch
            torch.manual_seed(seed)
        wavs, sr = model.generate_voice_clone(text=text, language="Korean", ref_audio=str(ref_audio), ref_text=ref_text)
    return np.asarray(wavs[0], dtype=np.float32), int(sr)


app = make_app(synthesize, "qwen3-tts")

if __name__ == "__main__":
    run(app, 8081)
