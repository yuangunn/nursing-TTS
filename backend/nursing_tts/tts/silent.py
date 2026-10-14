"""Placeholder engine: produces near-silent audio sized like real speech.

Useful for testing the whole pipeline (file naming, mixing, batch jobs) on
machines without a TTS model.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np


class SilentEngine:
    key = "silent"
    label = "무음 테스트 엔진 (음성 없음)"
    clones_voice = False

    def __init__(self, sr: int = 24000):
        self.sr = sr

    def available(self) -> tuple[bool, str]:
        return True, "항상 사용 가능 (테스트 전용)"

    def synthesize(self, text: str, ref: tuple[Path, str] | None, seed: int | None = None) -> tuple[np.ndarray, int]:
        syllables = sum(1 for ch in text if "가" <= ch <= "힣" or ch.isalnum())
        dur = max(0.4, syllables * 0.17)
        rng = np.random.default_rng(seed)
        n = int(dur * self.sr)
        t = np.arange(n) / self.sr
        # very quiet hum so the file is audibly "something"
        audio = 0.02 * np.sin(2 * np.pi * 220 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t))
        audio += 0.002 * rng.standard_normal(n)
        return audio.astype(np.float32), self.sr
