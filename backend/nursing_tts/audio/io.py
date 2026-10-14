"""WAV/FLAC/OGG read & write plus resampling, with no ffmpeg dependency."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


def _ffmpeg() -> str | None:
    import shutil
    return shutil.which("ffmpeg")


def _decode_with_ffmpeg(path: Path, sr: int) -> np.ndarray:
    """Decode any container ffmpeg understands (m4a/aac, mp3, webm, ...) to mono float32."""
    import subprocess
    exe = _ffmpeg()
    if not exe:
        raise RuntimeError("이 형식은 ffmpeg가 있어야 읽을 수 있습니다 (m4a/aac/mp3/webm). ffmpeg를 설치하거나 wav로 변환해 주세요.")
    cmd = [exe, "-v", "error", "-i", str(path), "-f", "f32le", "-acodec", "pcm_f32le", "-ac", "1", "-ar", str(sr), "-"]
    out = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype=np.float32).copy()


def read_audio(path: str | Path, target_sr: int | None = None) -> tuple[np.ndarray, int]:
    path = Path(path)
    try:
        data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    except Exception:  # libsndfile cannot open m4a/aac, some mp3, webm/opus ...
        sr = target_sr or 24000
        return _decode_with_ffmpeg(path, sr), sr
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
