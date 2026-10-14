"""Mixes synthesised speech with scheduled ambient noise events."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

from . import noise as noise_mod
from .io import read_audio, rms


@dataclass
class NoiseClip:
    """A user-uploaded noise file."""
    id: str
    label: str
    path: Path
    category: str = "custom"
    continuous: bool = False
    gain: float = 0.5


@dataclass
class NoiseConfig:
    enabled: bool = False
    level: int = 35                     # 0..100 loudness of the ambience
    types: list[str] = field(default_factory=lambda: ["room_tone", "monitor_pulse", "crowd_babble", "footsteps"])
    density: float = 4.0                # events per minute
    reverb: bool = False
    seed: int | None = None
    head_pad: float = 0.6               # silence before speech (s)
    tail_pad: float = 0.8


def level_to_snr_db(level: int) -> float:
    """0 -> +35 dB (nearly silent), 100 -> +4 dB (very busy ward)."""
    level = max(0, min(100, int(level)))
    return 35.0 - 0.31 * level


def _synthetic_ir(sr: int, rng: np.random.Generator, t60: float = 0.35) -> np.ndarray:
    n = int(t60 * sr)
    t = np.arange(n) / sr
    ir = rng.standard_normal(n).astype(np.float32) * np.exp(-6.9 * t / t60).astype(np.float32)
    ir = sosfilt(butter(2, 4000, btype="low", fs=sr, output="sos"), ir).astype(np.float32)
    ir[0] = 1.0
    return ir / (np.max(np.abs(ir)) + 1e-9)


def apply_room(audio: np.ndarray, sr: int, rng: np.random.Generator, wet: float = 0.18) -> np.ndarray:
    ir = _synthetic_ir(sr, rng)
    tail = fftconvolve(audio, ir)[: len(audio)].astype(np.float32)
    tail /= (np.max(np.abs(tail)) + 1e-9)
    tail *= float(np.max(np.abs(audio)))
    return ((1 - wet) * audio + wet * tail).astype(np.float32)


def _fit(clip: np.ndarray, n: int, rng: np.random.Generator) -> np.ndarray:
    if len(clip) >= n:
        start = int(rng.integers(0, len(clip) - n + 1))
        return clip[start:start + n]
    reps = int(np.ceil(n / max(1, len(clip))))
    return np.tile(clip, reps)[:n]


def _distant(clip: np.ndarray, sr: int, rng: np.random.Generator) -> np.ndarray:
    """Make a speech clip sound like it's from the next bed / corridor."""
    out = sosfilt(butter(2, [250, 2600], btype="band", fs=sr, output="sos"), clip).astype(np.float32)
    out = apply_room(out, sr, rng, wet=0.35)
    return out / (np.max(np.abs(out)) + 1e-9)


def mix(speech: np.ndarray, sr: int, cfg: NoiseConfig, custom: list[NoiseClip] | None = None,
        extra_voices: list[tuple[np.ndarray, str]] | None = None) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Return (mixed audio, list of scheduled events)."""
    rng = np.random.default_rng(cfg.seed)
    head = np.zeros(int(cfg.head_pad * sr), dtype=np.float32)
    tail = np.zeros(int(cfg.tail_pad * sr), dtype=np.float32)
    speech = np.concatenate([head, speech.astype(np.float32), tail])
    n = len(speech)
    dur = n / sr
    events: list[dict[str, Any]] = []

    if not cfg.enabled:
        return speech, events

    custom = custom or []
    custom_map = {c.id: c for c in custom}
    types = [t for t in cfg.types if t in noise_mod.BUILTIN or t in custom_map]
    if not types and not extra_voices:
        return speech, events

    bed = np.zeros(n, dtype=np.float32)
    layer = np.zeros(n, dtype=np.float32)

    # --- continuous bed layers
    for t in types:
        if t in noise_mod.BUILTIN and noise_mod.BUILTIN[t].continuous:
            bed += noise_mod.render(t, dur, sr, rng, n=n) * noise_mod.BUILTIN[t].gain
            events.append({"type": t, "start": 0.0, "duration": round(dur, 2)})
        elif t in custom_map and custom_map[t].continuous:
            clip, _ = read_audio(custom_map[t].path, sr)
            bed += _fit(clip, n, rng) * custom_map[t].gain
            events.append({"type": t, "start": 0.0, "duration": round(dur, 2)})

    # --- scheduled events
    event_types = [t for t in types if not (t in noise_mod.BUILTIN and noise_mod.BUILTIN[t].continuous)
                   and not (t in custom_map and custom_map[t].continuous)]
    if event_types:
        count = max(1, int(round(cfg.density * dur / 60.0 * float(rng.uniform(0.7, 1.3)))))
        for _ in range(count):
            t = str(rng.choice(event_types))
            if t in noise_mod.BUILTIN:
                nt = noise_mod.BUILTIN[t]
                d = float(rng.uniform(nt.min_dur, nt.max_dur))
                d = min(d, dur)
                start = float(rng.uniform(0, max(0.01, dur - d)))
                clip = noise_mod.render(t, d, sr, rng) * nt.gain * float(rng.uniform(0.6, 1.0))
            else:
                c = custom_map[t]
                raw, _ = read_audio(c.path, sr)
                d = min(len(raw) / sr, dur)
                start = float(rng.uniform(0, max(0.01, dur - d)))
                clip = _fit(raw, int(d * sr), rng) * c.gain * float(rng.uniform(0.6, 1.0))
            i = int(start * sr)
            seg = clip[: max(0, n - i)]
            # fade edges so events don't click
            fade = min(len(seg) // 4, int(0.3 * sr))
            if fade > 0:
                seg = seg.copy()
                seg[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
                seg[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
            layer[i:i + len(seg)] += seg
            events.append({"type": t, "start": round(start, 2), "duration": round(len(seg) / sr, 2)})

    # --- other voices (doctor rounds etc.) rendered by TTS and placed far away
    for clip, label in extra_voices or []:
        clip = _distant(clip.astype(np.float32), sr, rng)
        d = min(len(clip) / sr, dur)
        start = float(rng.uniform(0, max(0.01, dur - d)))
        i = int(start * sr)
        seg = clip[: max(0, min(len(clip), n - i))] * 0.6
        layer[i:i + len(seg)] += seg
        events.append({"type": f"voice:{label}", "start": round(start, 2), "duration": round(len(seg) / sr, 2)})

    ambience = bed + layer
    # --- scale ambience to the requested SNR against the speech
    s_rms = rms(speech)
    a_rms = rms(ambience)
    if a_rms > 1e-6 and s_rms > 1e-6:
        snr = level_to_snr_db(cfg.level)
        target = s_rms / (10 ** (snr / 20))
        ambience *= target / a_rms

    out = speech + ambience
    if cfg.reverb:
        out = apply_room(out, sr, rng)
    peak = float(np.max(np.abs(out)))
    if peak > 0.98:
        out = out / peak * 0.98
    return out.astype(np.float32), events
