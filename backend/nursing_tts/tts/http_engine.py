"""Generic HTTP voice-cloning server adapter.

Contract (so any model - Fish Speech, CosyVoice, XTTS, GPT-SoVITS... - can be
wrapped with a few lines of Python):

    POST {url}  multipart/form-data
        text       : phonetic Korean text to speak
        ref_audio  : reference wav file (optional)
        ref_text   : transcript of ref_audio (optional)
        seed       : int (optional)
    -> 200 audio/wav body (mono or stereo, any sample rate)

See ``scripts/example_tts_server.py`` for a reference implementation.
"""
from __future__ import annotations

import io
from pathlib import Path

import httpx
import numpy as np
import soundfile as sf

from ..audio.io import resample


class HttpTTSEngine:
    key = "http"
    label = "커스텀 HTTP TTS 서버 (Fish Speech, CosyVoice 등 래핑)"
    clones_voice = True

    def __init__(self, url: str, sr: int = 24000, timeout: float = 600.0):
        self.url = url
        self.sr = sr
        self.timeout = timeout

    def available(self) -> tuple[bool, str]:
        if not self.url:
            return False, "URL 미설정"
        try:
            r = httpx.get(self.url.rsplit("/", 1)[0] + "/health", timeout=3.0)
            return r.status_code < 500, f"{self.url} ({r.status_code})"
        except Exception as e:  # noqa: BLE001
            return False, f"연결 실패: {e}"

    def synthesize(self, text: str, ref: tuple[Path, str] | None, seed: int | None = None) -> tuple[np.ndarray, int]:
        data = {"text": text}
        if seed is not None:
            data["seed"] = str(seed)
        files = {}
        if ref:
            path, ref_text = ref
            data["ref_text"] = ref_text
            files["ref_audio"] = (path.name, path.read_bytes(), "audio/wav")
        r = httpx.post(self.url, data=data, files=files or None, timeout=self.timeout)
        r.raise_for_status()
        audio, sr = sf.read(io.BytesIO(r.content), dtype="float32", always_2d=True)
        mono = audio.mean(axis=1).astype(np.float32)
        if sr != self.sr:
            mono = resample(mono, sr, self.sr)
            sr = self.sr
        return mono, sr
