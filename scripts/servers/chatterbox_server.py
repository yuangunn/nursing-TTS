"""Chatterbox Multilingual wrapper (Resemble AI, MIT; 23 languages incl. Korean `ko`).

Setup:
    pip install chatterbox-tts fastapi uvicorn python-multipart soundfile
    python scripts/servers/chatterbox_server.py --port 8082
App settings → 커스텀 HTTP TTS 서버 URL: http://127.0.0.1:8082/synthesize

API per https://github.com/resemble-ai/chatterbox:
    model = ChatterboxMultilingualTTS.from_pretrained(device="cuda", t3_model="v3")
    wav = model.generate(text, language_id="ko", audio_prompt_path=ref)   # tensor, model.sr
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from _common import make_app, run  # noqa: E402

_model = None
_lock = threading.Lock()


def _device() -> str:
    import torch
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _load():
    global _model
    if _model is None:
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        try:
            _model = ChatterboxMultilingualTTS.from_pretrained(device=_device(), t3_model="v3")
        except TypeError:  # older package without the v3 selector
            _model = ChatterboxMultilingualTTS.from_pretrained(device=_device())
    return _model


def synthesize(text: str, ref_audio: Path | None, ref_text: str, seed: int | None):
    model = _load()
    with _lock:
        if seed is not None:
            import torch
            torch.manual_seed(seed)
        kwargs = {"language_id": "ko"}
        if ref_audio is not None:
            kwargs["audio_prompt_path"] = str(ref_audio)
        wav = model.generate(text, **kwargs)
    audio = wav.detach().cpu().numpy() if hasattr(wav, "detach") else np.asarray(wav)
    return np.asarray(audio, dtype=np.float32).reshape(-1), int(model.sr)


app = make_app(synthesize, "chatterbox-multilingual")

if __name__ == "__main__":
    run(app, 8082)
