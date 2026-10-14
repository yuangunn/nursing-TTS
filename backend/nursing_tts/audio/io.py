"""WAV/FLAC/OGG read & write plus resampling, with no ffmpeg dependency."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


def read_audio(path: str | Path, target_sr: int | None = None) -> tuple[np.ndarray, int]:
    data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    mono = data.mean(axis=1)
    if target_sr and sr != target_sr:
        mono = resample(mono, sr, target_sr)
        sr = target_sr
    return mono.astype(np.float32), sr


def write_wav(path: str | Path, audio: np.ndarray, sr: int, subtype: str = "PCM_16") -> None:
    audio = np.clip(audio, -1.0, 1.0).astype(np.float32)
    sf.write(str(path), audio, sr, subtype=subtype)


def resample(audio: np.ndarray, sr_from: int, sr_to: int) -> np.ndarray:
    if sr_from == sr_to:
        return audio
    from math import gcd
    g = gcd(sr_from, sr_to)
    return resample_poly(audio, sr_to // g, sr_from // g).astype(np.float32)


def duration(path: str | Path) -> float:
    info = sf.info(str(path))
    return info.frames / info.samplerate


def rms(audio: np.ndarray) -> float:
    if audio.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(audio))))


def normalize_peak(audio: np.ndarray, peak: float = 0.95) -> np.ndarray:
    m = float(np.max(np.abs(audio))) if audio.size else 0.0
    if m < 1e-6:
        return audio
    return (audio / m * peak).astype(np.float32)
