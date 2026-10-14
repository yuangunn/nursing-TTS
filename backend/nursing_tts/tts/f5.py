"""F5-TTS adapter (local zero-shot voice cloning).

Install with ``pip install -r requirements-f5.txt``.  The stock F5-TTS base
checkpoint is English/Chinese; for Korean, point ``f5_ckpt_file`` and
``f5_vocab_file`` at a Korean fine-tuned checkpoint (see README).
"""
from __future__ import annotations

import importlib.util
import threading
from pathlib import Path

import numpy as np

from ..audio.io import resample


def _pick_device(pref: str) -> str:
    if pref and pref != "auto":
        return pref
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except Exception:  # noqa: BLE001
        pass
    return "cpu"


class F5Engine:
    key = "f5"
    label = "F5-TTS (로컬 목소리 복제)"
    clones_voice = True

    def __init__(self, model: str = "F5TTS_v1_Base", ckpt_file: str = "", vocab_file: str = "",
                 device: str = "auto", nfe_step: int = 32, speed: float = 1.0, sr: int = 24000):
        self.model = model
        self.ckpt_file = ckpt_file
        self.vocab_file = vocab_file
        self.device_pref = device
        self.nfe_step = int(nfe_step)
        self.speed = float(speed)
        self.sr = sr
        self._f5 = None
        self._lock = threading.Lock()
        self._error = ""

    def available(self) -> tuple[bool, str]:
        if importlib.util.find_spec("f5_tts") is None:
            return False, "f5-tts 패키지 미설치 (pip install -r requirements-f5.txt)"
        if self.ckpt_file and not Path(self.ckpt_file).exists():
            return False, f"체크포인트 파일 없음: {self.ckpt_file}"
        dev = _pick_device(self.device_pref)
        note = "" if self.ckpt_file else " · 기본 체크포인트는 영/중 모델입니다. 한국어 체크포인트를 설정하세요."
        return True, f"device={dev}{note}"

    def _load(self):
        if self._f5 is not None:
            return self._f5
        with self._lock:
            if self._f5 is None:
                from f5_tts.api import F5TTS  # type: ignore
                kwargs = {"model": self.model, "device": _pick_device(self.device_pref)}
                if self.ckpt_file:
                    kwargs["ckpt_file"] = self.ckpt_file
                if self.vocab_file:
                    kwargs["vocab_file"] = self.vocab_file
                self._f5 = F5TTS(**kwargs)
        return self._f5

    def synthesize(self, text: str, ref: tuple[Path, str] | None, seed: int | None = None) -> tuple[np.ndarray, int]:
        if ref is None:
            raise RuntimeError("F5-TTS는 참조 음성(등록된 목소리)이 필요합니다.")
        f5 = self._load()
        ref_path, ref_text = ref
        with self._lock:
            wav, sr, _spec = f5.infer(
                ref_file=str(ref_path),
                ref_text=ref_text,
                gen_text=text,
                nfe_step=self.nfe_step,
                speed=self.speed,
                seed=seed,
                show_info=lambda *a, **k: None,
                progress=None,
            )
        audio = np.asarray(wav, dtype=np.float32)
        if audio.ndim > 1:
            audio = audio.mean(axis=-1)
        if sr != self.sr:
            audio = resample(audio, sr, self.sr)
            sr = self.sr
        return audio, sr
