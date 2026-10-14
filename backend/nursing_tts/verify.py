"""ASR round-trip verification (idea borrowed from TTS dataset generators):
transcribe the generated audio with a local Whisper model and compare it to
the intended text.  Clips whose character error rate exceeds a threshold are
flagged so they can be reviewed or regenerated instead of polluting the
training set.

Optional dependency: ``pip install faster-whisper``.
"""
from __future__ import annotations

import importlib.util
import re
import threading
from pathlib import Path
from typing import Any

_MODEL = None
_MODEL_KEY = None
_LOCK = threading.Lock()


def available() -> tuple[bool, str]:
    if importlib.util.find_spec("faster_whisper") is None:
        return False, "faster-whisper 미설치 (pip install faster-whisper)"
    return True, "faster-whisper"


_PUNCT = re.compile(r"[^\w가-힣]+", re.UNICODE)


def normalize(text: str) -> str:
    text = text.replace("\n", " ")
    text = _PUNCT.sub("", text)
    return text.lower()


def cer(ref: str, hyp: str) -> float:
    """Character error rate via Levenshtein distance on normalized strings."""
    r = normalize(ref)
    h = normalize(hyp)
    if not r:
        return 0.0 if not h else 1.0
    prev = list(range(len(h) + 1))
    for i, rc in enumerate(r, start=1):
        cur = [i]
        for j, hc in enumerate(h, start=1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rc != hc)))
        prev = cur
    return prev[-1] / len(r)


def _load(model_size: str, device: str):
    global _MODEL, _MODEL_KEY
    key = (model_size, device)
    with _LOCK:
        if _MODEL is None or _MODEL_KEY != key:
            from faster_whisper import WhisperModel  # type: ignore

            dev = device
            compute = "float16"
            if device == "auto":
                try:
                    import torch
                    dev = "cuda" if torch.cuda.is_available() else "cpu"
                except Exception:  # noqa: BLE001
                    dev = "cpu"
            if dev != "cuda":
                compute = "int8"
            _MODEL = WhisperModel(model_size, device=dev, compute_type=compute)
            _MODEL_KEY = key
    return _MODEL


def transcribe(path: Path, model_size: str = "small", device: str = "auto") -> str:
    model = _load(model_size, device)
    segments, _info = model.transcribe(str(path), language="ko", beam_size=1, vad_filter=False)
    return " ".join(s.text.strip() for s in segments)


def verify(path: Path, spoken_text: str, tts_text: str, settings: dict[str, Any]) -> dict[str, Any]:
    """Return {hyp, cer, cer_phonetic, passed}.  Never raises; errors are reported in the dict."""
    try:
        hyp = transcribe(path, settings.get("asr_model") or "small", settings.get("asr_device") or "auto")
    except Exception as e:  # noqa: BLE001
        return {"error": str(e), "passed": None}
    c1 = cer(spoken_text, hyp)
    c2 = cer(tts_text, hyp)
    best = min(c1, c2)
    thr = float(settings.get("cer_threshold", 0.25))
    return {"hyp": hyp, "cer": round(c1, 4), "cer_phonetic": round(c2, 4), "cer_best": round(best, 4),
            "threshold": thr, "passed": best <= thr}
