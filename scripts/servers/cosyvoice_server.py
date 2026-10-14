"""Fun-CosyVoice3 / CosyVoice2 wrapper (Alibaba, Apache-2.0; Korean among 9 languages).

Setup (run from a clone of https://github.com/FunAudioLLM/CosyVoice with its conda env and
`pretrained_models/Fun-CosyVoice3-0.5B` downloaded; see that repo's README):
    pip install fastapi uvicorn python-multipart soundfile
    COSYVOICE_ROOT=/path/to/CosyVoice python scripts/servers/cosyvoice_server.py --port 8083
App settings → 커스텀 HTTP TTS 서버 URL: http://127.0.0.1:8083/synthesize

API per the repo's example.py:
    cosyvoice = AutoModel(model_dir='pretrained_models/Fun-CosyVoice3-0.5B')
    for j in cosyvoice.inference_zero_shot(text, 'You are a helpful assistant.<|endofprompt|>' + prompt_text, prompt_wav, stream=False):
        j['tts_speech'], cosyvoice.sample_rate
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from _common import make_app, run  # noqa: E402

ROOT = Path(os.environ.get("COSYVOICE_ROOT", ".")).resolve()
MODEL_DIR = os.environ.get("COSYVOICE_MODEL", str(ROOT / "pretrained_models" / "Fun-CosyVoice3-0.5B"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "third_party" / "Matcha-TTS"))

_model = None
_lock = threading.Lock()


def _load():
    global _model
    if _model is None:
        from cosyvoice.cli.cosyvoice import AutoModel
        _model = AutoModel(model_dir=MODEL_DIR)
    return _model


def synthesize(text: str, ref_audio: Path | None, ref_text: str, seed: int | None):
    if ref_audio is None:
        raise RuntimeError("ref_audio is required for zero-shot cloning")
    model = _load()
    prompt = ref_text
    if "CosyVoice3" in MODEL_DIR and "<|endofprompt|>" not in prompt:
        prompt = "You are a helpful assistant.<|endofprompt|>" + ref_text
    with _lock:
        if seed is not None:
            import torch
            torch.manual_seed(seed)
        pieces = [j["tts_speech"] for j in model.inference_zero_shot(text, prompt, str(ref_audio), stream=False)]
    import torch
    audio = torch.cat(pieces, dim=-1).reshape(-1).cpu().numpy()
    return np.asarray(audio, dtype=np.float32), int(model.sample_rate)


app = make_app(synthesize, "cosyvoice")

if __name__ == "__main__":
    run(app, 8083)
