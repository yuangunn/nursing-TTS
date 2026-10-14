"""TTS engine interface."""
from __future__ import annotations

import random
from pathlib import Path
from typing import Protocol

import numpy as np


class TTSEngine(Protocol):
    key: str
    label: str
    clones_voice: bool

    def available(self) -> tuple[bool, str]:
        """(is_available, human readable status)."""

    def synthesize(self, text: str, ref: tuple[Path, str] | None, seed: int | None = None) -> tuple[np.ndarray, int]:
        """Synthesize one chunk of phonetic Korean text -> (mono float32, sample_rate)."""


def synthesize_paragraphs(engine: TTSEngine, paragraphs: list[str], ref: tuple[Path, str] | None,
                          seed: int | None, pause_range: tuple[float, float] = (0.35, 0.8),
                          progress=None) -> tuple[np.ndarray, int]:
    """Synthesize each paragraph separately and join them with natural pauses."""
    rng = random.Random(seed)
    pieces: list[np.ndarray] = []
    sr = 24000
    total = len(paragraphs)
    for i, para in enumerate(paragraphs):
        para = para.strip()
        if not para:
            continue
        audio, sr = engine.synthesize(para, ref, seed=(seed + i) if seed is not None else None)
        pieces.append(audio.astype(np.float32))
        if i < total - 1:
            pause = rng.uniform(*pause_range)
            pieces.append(np.zeros(int(pause * sr), dtype=np.float32))
        if progress:
            progress(i + 1, total)
    if not pieces:
        return np.zeros(int(0.5 * sr), dtype=np.float32), sr
    return np.concatenate(pieces), sr
