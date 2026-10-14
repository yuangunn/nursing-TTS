"""Channel / microphone simulation and speed perturbation.

Borrowed from ASR data-augmentation practice (Kaldi speed perturbation,
MUSAN-style noise, band-limited "telephone" channels): the same utterance is
rendered as if captured on different devices so a model trained on the
corpus does not overfit a single clean studio condition.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import gcd

import numpy as np
from scipy.signal import butter, resample_poly, sosfilt


@dataclass
class ChannelPreset:
    key: str
    label: str
    low: float          # high-pass cutoff (Hz)
    high: float         # low-pass cutoff (Hz)
    noise_floor: float  # white-noise floor relative to speech RMS (dB, negative)
    drive: float        # soft clipping amount (0 = none)
    tilt_db: float      # spectral tilt: + brightens, - muffles
    resonance: float    # mid bump amount for cheap mics
    order: int = 4


PRESETS: dict[str, ChannelPreset] = {
    "studio": ChannelPreset("studio", "스튜디오/근접 마이크 (원음)", 20, 20000, -70, 0.0, 0.0, 0.0),
    "smartphone": ChannelPreset("smartphone", "스마트폰 내장 마이크", 90, 9000, -52, 0.05, 1.5, 0.3),
    "lapel": ChannelPreset("lapel", "핀 마이크 (옷깃)", 70, 12000, -58, 0.0, -0.5, 0.15),
    "recorder": ChannelPreset("recorder", "휴대용 녹음기 (저음질)", 120, 6500, -46, 0.08, -1.0, 0.45),
    "telephone": ChannelPreset("telephone", "전화/무전 대역 (300~3400Hz)", 300, 3400, -42, 0.12, 0.0, 0.2, order=6),
    "distant": ChannelPreset("distant", "책상 위 멀리 놓은 폰 (울림)", 100, 7000, -48, 0.0, -2.0, 0.2),
    "headset": ChannelPreset("headset", "헤드셋/블루투스 이어폰", 150, 7500, -50, 0.04, 0.5, 0.35),
}


@dataclass
class AugmentConfig:
    enabled: bool = False
    channels: list[str] = field(default_factory=lambda: ["studio", "smartphone", "lapel", "recorder"])
    speed_min: float = 0.92
    speed_max: float = 1.08
    speed_prob: float = 0.6
    gain_db_range: float = 6.0       # random gain within +-range
    clip_prob: float = 0.1           # probability of mild overload clipping


def _tilt(audio: np.ndarray, sr: int, db: float) -> np.ndarray:
    if abs(db) < 0.1:
        return audio
    sos = butter(1, 2000, btype="high" if db > 0 else "low", fs=sr, output="sos")
    shelf = sosfilt(sos, audio).astype(np.float32)
    g = 10 ** (abs(db) / 20) - 1
    return (audio + g * shelf) / (1 + g * 0.5)


def _mid_bump(audio: np.ndarray, sr: int, amount: float) -> np.ndarray:
    if amount <= 0:
        return audio
    sos = butter(2, [1800, 3600], btype="band", fs=sr, output="sos")
    return (audio + amount * sosfilt(sos, audio)).astype(np.float32)


def _soft_clip(audio: np.ndarray, drive: float) -> np.ndarray:
    if drive <= 0:
        return audio
    k = 1 + drive * 8
    return (np.tanh(audio * k) / np.tanh(k)).astype(np.float32)


def apply_channel(audio: np.ndarray, sr: int, preset: ChannelPreset, rng: np.random.Generator) -> np.ndarray:
    out = audio.astype(np.float32)
    nyq = sr / 2
    low = max(10.0, min(preset.low, nyq - 100))
    high = min(preset.high, nyq - 100)
    if low > 20:
        out = sosfilt(butter(preset.order, low, btype="high", fs=sr, output="sos"), out).astype(np.float32)
    if high < nyq - 200:
        out = sosfilt(butter(preset.order, high, btype="low", fs=sr, output="sos"), out).astype(np.float32)
    out = _tilt(out, sr, preset.tilt_db)
    out = _mid_bump(out, sr, preset.resonance)
    out = _soft_clip(out, preset.drive)
    rms = float(np.sqrt(np.mean(out ** 2))) or 1e-4
    floor = rms * 10 ** (preset.noise_floor / 20)
    if floor > 1e-6:
        out = out + rng.standard_normal(len(out)).astype(np.float32) * floor
    if preset.key == "distant":
        # cheap early reflections
        for delay_ms, g in ((11, 0.35), (23, 0.22), (37, 0.15)):
            d = int(delay_ms * sr / 1000)
            if d < len(out):
                out[d:] += g * out[:-d]
        out *= 0.7
    return out


def speed_perturb(audio: np.ndarray, factor: float) -> np.ndarray:
    """Kaldi-style speed perturbation (resampling: pitch shifts slightly with tempo)."""
    if abs(factor - 1.0) < 1e-3:
        return audio
    num = int(round(1000 / factor))
    den = 1000
    g = gcd(num, den)
    return resample_poly(audio, num // g, den // g).astype(np.float32)


def augment(audio: np.ndarray, sr: int, cfg: AugmentConfig, rng: np.random.Generator) -> tuple[np.ndarray, dict]:
    """Returns (audio, info).  Applied to the *speech* before noise mixing."""
    info: dict = {"channel": "studio", "speed": 1.0, "gain_db": 0.0, "clipped": False}
    if not cfg.enabled:
        return audio.astype(np.float32), info
    out = audio.astype(np.float32)
    if cfg.speed_prob > 0 and rng.random() < cfg.speed_prob:
        f = float(rng.uniform(cfg.speed_min, cfg.speed_max))
        out = speed_perturb(out, f)
        info["speed"] = round(f, 3)
    choices = [c for c in cfg.channels if c in PRESETS] or ["studio"]
    key = str(rng.choice(choices))
    out = apply_channel(out, sr, PRESETS[key], rng)
    info["channel"] = key
    if cfg.gain_db_range > 0:
        g = float(rng.uniform(-cfg.gain_db_range, cfg.gain_db_range))
        out = out * (10 ** (g / 20))
        info["gain_db"] = round(g, 2)
    if cfg.clip_prob > 0 and rng.random() < cfg.clip_prob:
        out = np.clip(out * 1.8, -0.98, 0.98)
        info["clipped"] = True
    peak = float(np.max(np.abs(out))) if out.size else 0.0
    if peak > 0.98:
        out = out / peak * 0.98
    return out.astype(np.float32), info


def preset_catalogue() -> list[dict]:
    return [{"key": p.key, "label": p.label} for p in PRESETS.values()]
