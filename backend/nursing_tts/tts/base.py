"""TTS engine interface."""
from __future__ import annotations

import math
import random
import re
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


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def chunk_sentences(paragraph: str, min_chars: int = 20) -> list[str]:
    """Split a paragraph into sentences; very short ones ride along with the previous sentence
    (autoregressive TTS truncates/hallucinates on 2-3 word inputs)."""
    out: list[str] = []
    for s in _SENT_SPLIT.split(paragraph.strip()):
        if not s.strip():
            continue
        if out and len(re.sub(r"\s", "", out[-1])) < min_chars:
            out[-1] = f"{out[-1]} {s}"
        else:
            out.append(s)
    if len(out) > 1 and len(re.sub(r"\s", "", out[-1])) < min_chars:  # trailing "끝." rides with the previous one
        last = out.pop()
        out[-1] = f"{out[-1]} {last}"
    return out


def trim_silence(audio: np.ndarray, sr: int, threshold: float = 0.004, keep: float = 0.05) -> np.ndarray:
    """Cut the model's own leading/trailing silence so the pause between chunks is ours alone
    (Qwen sometimes appends 2-3 s of silence; combined with our pause that gave 7 s gaps)."""
    n = int(0.01 * sr)
    if len(audio) < 2 * n:
        return audio
    count = len(audio) // n
    e = np.sqrt(np.mean(audio[: count * n].reshape(count, n) ** 2, axis=1))
    idx = np.flatnonzero(e > threshold)
    if len(idx) == 0:
        return audio
    k = int(keep * sr)
    a = max(0, idx[0] * n - k)
    b = min(len(audio), (idx[-1] + 1) * n + k)
    return audio[a:b]


def natural_pause(rng: random.Random, scale: float = 1.0) -> float:
    """Pause length in seconds. Log-normal fitted to three real nurse dictations (2026-10-15):
    median 0.6 s, p90 1.6 s, a few 2-4 s; section changes (scale ~1.6) run longer."""
    return min(3.5, max(0.25, rng.lognormvariate(math.log(0.6 * scale), 0.75)))


def synthesize_paragraphs(engine: TTSEngine, paragraphs: list[str], ref: tuple[Path, str] | None,
                          seed: int | None, progress=None) -> tuple[np.ndarray, int]:
    """Synthesize sentence chunks separately and join them with natural pauses.

    Pauses between sentences follow the real-recording distribution; paragraph (section) changes get
    longer ones.  Synthesizing per sentence also gives the model shorter inputs."""
    rng = random.Random(seed)
    pieces: list[np.ndarray] = []
    sr = 24000
    total = len(paragraphs)
    k = 0
    for i, para in enumerate(paragraphs):
        chunks = chunk_sentences(para)
        for j, chunk in enumerate(chunks):
            audio, sr = engine.synthesize(chunk, ref, seed=(seed + k) if seed is not None else None)
            k += 1
            pieces.append(trim_silence(audio.astype(np.float32), sr))
            last_chunk = j == len(chunks) - 1
            if not (last_chunk and i == total - 1):
                pause = natural_pause(rng, 1.6 if last_chunk else 1.0)
                pieces.append(np.zeros(int(pause * sr), dtype=np.float32))
        if progress:
            progress(i + 1, total)
    if not pieces:
        return np.zeros(int(0.5 * sr), dtype=np.float32), sr
    return np.concatenate(pieces), sr
