"""Procedurally synthesised hospital-ward ambience.

Everything here is pure numpy/scipy so that it works on every platform with
no sample files.  Real recordings can be added through the noise library and
are mixed with the same event scheduler (see ``mixer.py``).
"""
from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, lfilter, sosfilt


def _sos(kind: str, cutoff, sr: int, order: int = 4):
    return butter(order, cutoff, btype=kind, fs=sr, output="sos")


def pink_noise(n: int, rng: np.random.Generator) -> np.ndarray:
    """Voss-McCartney-ish pink noise via FFT shaping."""
    white = rng.standard_normal(n).astype(np.float32)
    spec = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n)
    freqs[0] = freqs[1] if n > 1 else 1.0
    spec = spec / np.sqrt(freqs)
    pink = np.fft.irfft(spec, n).astype(np.float32)
    return pink / (np.max(np.abs(pink)) + 1e-9)


def _env(n: int, attack: int, release: int) -> np.ndarray:
    env = np.ones(n, dtype=np.float32)
    a = min(attack, n)
    r = min(release, n)
    env[:a] = np.linspace(0, 1, a, dtype=np.float32)
    env[n - r:] *= np.linspace(1, 0, r, dtype=np.float32)
    return env


def tone(freq: float, dur: float, sr: int, amp: float = 0.5, harmonics: int = 1) -> np.ndarray:
    t = np.arange(int(dur * sr)) / sr
    out = np.zeros_like(t, dtype=np.float32)
    for h in range(1, harmonics + 1):
        out += (amp / h) * np.sin(2 * np.pi * freq * h * t).astype(np.float32)
    return out * _env(len(t), int(0.004 * sr), int(0.02 * sr))


# ---------------------------------------------------------------------------
# Generators: each returns mono float32 at ``sr`` with peak ~<= 1
# ---------------------------------------------------------------------------

def room_tone(dur: float, sr: int, rng: np.random.Generator) -> np.ndarray:
    n = int(dur * sr)
    pn = pink_noise(n, rng)
    # HVAC hum: lowpassed noise + 60/120 Hz rumble
    pn = sosfilt(_sos("low", 1800, sr), pn).astype(np.float32)
    t = np.arange(n) / sr
    hum = 0.08 * np.sin(2 * np.pi * 60 * t) + 0.04 * np.sin(2 * np.pi * 120 * t)
    out = 0.6 * pn + hum.astype(np.float32)
    return out / (np.max(np.abs(out)) + 1e-9)


def monitor_pulse(dur: float, sr: int, rng: np.random.Generator, hr: float | None = None) -> np.ndarray:
    """Pulse-oximeter beep at ~heart rate; pitch tracks SpO2 (fixed here)."""
    hr = hr or float(rng.uniform(62, 95))
    n = int(dur * sr)
    out = np.zeros(n, dtype=np.float32)
    beep = tone(float(rng.choice([880, 932, 988, 1046])), 0.07, sr, amp=0.6, harmonics=2)
    period = 60.0 / hr
    t = rng.uniform(0, period)
    while t < dur:
        i = int(t * sr)
        seg = beep[: max(0, min(len(beep), n - i))]
        out[i:i + len(seg)] += seg
        t += period * float(rng.uniform(0.97, 1.03))
    return out


def monitor_alarm(dur: float, sr: int, rng: np.random.Generator) -> np.ndarray:
    """Three-beep medium-priority alarm pattern repeated."""
    n = int(dur * sr)
    out = np.zeros(n, dtype=np.float32)
    f = float(rng.choice([1320, 1480, 1760]))
    beep = tone(f, 0.12, sr, amp=0.8, harmonics=3)
    gap = int(0.15 * sr)
    t = 0
    while t < n:
        for k in range(3):
            i = t + k * (len(beep) + gap)
            seg = beep[: max(0, min(len(beep), n - i))]
            if len(seg) == 0:
                break
            out[i:i + len(seg)] += seg
        t += int(1.6 * sr)
    return out


def iv_pump_alarm(dur: float, sr: int, rng: np.random.Generator) -> np.ndarray:
    n = int(dur * sr)
    out = np.zeros(n, dtype=np.float32)
    a = tone(2093, 0.18, sr, amp=0.7)
    b = tone(1568, 0.18, sr, amp=0.7)
    t = 0
    while t < n:
        for seg in (a, b):
            s = seg[: max(0, min(len(seg), n - t))]
            if len(s) == 0:
                break
            out[t:t + len(s)] += s
            t += len(seg) + int(0.08 * sr)
        t += int(0.5 * sr)
    return out


def nebulizer(dur: float, sr: int, rng: np.random.Generator) -> np.ndarray:
    n = int(dur * sr)
    white = rng.standard_normal(n).astype(np.float32)
    band = sosfilt(_sos("band", [600, 4500], sr), white).astype(np.float32)
    t = np.arange(n) / sr
    # compressor motor hum and slow flutter
    hum = 0.25 * np.sin(2 * np.pi * 100 * t) + 0.1 * np.sin(2 * np.pi * 200 * t)
    flutter = 1.0 + 0.15 * np.sin(2 * np.pi * float(rng.uniform(0.3, 0.8)) * t)
    out = (0.7 * band * flutter + hum).astype(np.float32)
    out *= _env(n, int(0.4 * sr), int(0.4 * sr))
    return out / (np.max(np.abs(out)) + 1e-9)


def crowd_babble(dur: float, sr: int, rng: np.random.Generator, voices: int = 8) -> np.ndarray:
    """Distant multi-talker babble: filtered noise with syllabic envelopes."""
    n = int(dur * sr)
    out = np.zeros(n, dtype=np.float32)
    t = np.arange(n) / sr
    for _ in range(voices):
        f0 = float(rng.uniform(110, 260))
        # buzz source with harmonics
        src = np.zeros(n, dtype=np.float32)
        for h in range(1, 12):
            src += (1.0 / h) * np.sin(2 * np.pi * f0 * h * t + rng.uniform(0, 6.28)).astype(np.float32)
        src += 0.4 * rng.standard_normal(n).astype(np.float32)
        # vowel-ish formant band
        lo, hi = sorted(rng.uniform(250, 2800, size=2))
        if hi - lo < 200:
            hi = lo + 200
        src = sosfilt(_sos("band", [lo, hi], sr, order=2), src).astype(np.float32)
        # syllabic envelope ~4 Hz, with pauses between utterances
        syl = 0.5 * (1 + np.sin(2 * np.pi * float(rng.uniform(3, 5.5)) * t + rng.uniform(0, 6.28)))
        gate = np.zeros(n, dtype=np.float32)
        pos = 0
        while pos < n:
            talk = int(rng.uniform(0.8, 3.0) * sr)
            pause = int(rng.uniform(0.5, 4.0) * sr)
            gate[pos:pos + talk] = 1.0
            pos += talk + pause
        env = (syl ** 2 * gate).astype(np.float32)
        out += src * env * float(rng.uniform(0.3, 1.0))
    # distance: muffle
    out = sosfilt(_sos("low", 2200, sr, order=2), out).astype(np.float32)
    return out / (np.max(np.abs(out)) + 1e-9)


def footsteps(dur: float, sr: int, rng: np.random.Generator) -> np.ndarray:
    n = int(dur * sr)
    out = np.zeros(n, dtype=np.float32)
    step = sosfilt(_sos("low", 400, sr), rng.standard_normal(int(0.06 * sr)).astype(np.float32))
    step = step * _env(len(step), int(0.002 * sr), int(0.05 * sr))
    step /= np.max(np.abs(step)) + 1e-9
    period = float(rng.uniform(0.45, 0.65))
    t = 0.0
    while t < dur:
        i = int(t * sr)
        seg = step[: max(0, min(len(step), n - i))]
        out[i:i + len(seg)] += seg * float(rng.uniform(0.5, 1.0))
        t += period * float(rng.uniform(0.9, 1.1))
    return out


def cart_rolling(dur: float, sr: int, rng: np.random.Generator) -> np.ndarray:
    n = int(dur * sr)
    white = rng.standard_normal(n).astype(np.float32)
    low = sosfilt(_sos("band", [80, 700], sr), white).astype(np.float32)
    t = np.arange(n) / sr
    rattle = 1.0 + 0.5 * np.sin(2 * np.pi * float(rng.uniform(6, 11)) * t)
    out = low * rattle * _env(n, int(0.5 * sr), int(0.5 * sr))
    # doppler-ish pass by: volume rises then falls
    out *= np.hanning(n).astype(np.float32)
    return out / (np.max(np.abs(out)) + 1e-9)


def door(dur: float, sr: int, rng: np.random.Generator) -> np.ndarray:
    n = int(max(dur, 0.6) * sr)
    out = np.zeros(n, dtype=np.float32)
    thud = sosfilt(_sos("low", 250, sr), rng.standard_normal(int(0.25 * sr)).astype(np.float32))
    thud *= _env(len(thud), int(0.003 * sr), int(0.2 * sr))
    out[: len(thud)] += thud / (np.max(np.abs(thud)) + 1e-9)
    click = tone(3200, 0.02, sr, amp=0.3)
    out[int(0.02 * sr):int(0.02 * sr) + len(click)] += click
    return out


def phone_ring(dur: float, sr: int, rng: np.random.Generator) -> np.ndarray:
    n = int(dur * sr)
    out = np.zeros(n, dtype=np.float32)
    t = np.arange(int(1.0 * sr)) / sr
    ring = (0.5 * np.sin(2 * np.pi * 1200 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 20 * t))).astype(np.float32)
    pos = 0
    while pos < n:
        seg = ring[: max(0, min(len(ring), n - pos))]
        out[pos:pos + len(seg)] += seg
        pos += int(3.0 * sr)
    return out


def keyboard(dur: float, sr: int, rng: np.random.Generator) -> np.ndarray:
    n = int(dur * sr)
    out = np.zeros(n, dtype=np.float32)
    t = 0.0
    while t < dur:
        click = sosfilt(_sos("high", 2500, sr), rng.standard_normal(int(0.015 * sr)).astype(np.float32))
        click *= _env(len(click), int(0.001 * sr), int(0.01 * sr))
        i = int(t * sr)
        seg = click[: max(0, min(len(click), n - i))]
        out[i:i + len(seg)] += seg * float(rng.uniform(0.3, 0.8))
        t += float(rng.uniform(0.08, 0.3))
    return out / (np.max(np.abs(out)) + 1e-9)


def curtain(dur: float, sr: int, rng: np.random.Generator) -> np.ndarray:
    n = int(max(dur, 1.0) * sr)
    white = rng.standard_normal(n).astype(np.float32)
    out = sosfilt(_sos("band", [1500, 6000], sr), white).astype(np.float32)
    t = np.arange(n) / sr
    out *= (0.5 + 0.5 * np.sin(2 * np.pi * 12 * t)).astype(np.float32)
    out *= _env(n, int(0.1 * sr), int(0.3 * sr))
    return out / (np.max(np.abs(out)) + 1e-9)


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

@dataclass
class NoiseType:
    key: str
    label: str
    fn: object
    min_dur: float
    max_dur: float
    gain: float        # relative loudness (1.0 = reference)
    continuous: bool   # bed layer vs. event


BUILTIN: dict[str, NoiseType] = {
    "room_tone": NoiseType("room_tone", "병실 룸톤 (공조 소음)", room_tone, 0, 0, 0.35, True),
    "monitor_pulse": NoiseType("monitor_pulse", "환자 모니터 맥박음", monitor_pulse, 8, 40, 0.25, False),
    "monitor_alarm": NoiseType("monitor_alarm", "모니터 알람", monitor_alarm, 3, 9, 0.45, False),
    "iv_pump_alarm": NoiseType("iv_pump_alarm", "수액 펌프 알람", iv_pump_alarm, 3, 8, 0.4, False),
    "nebulizer": NoiseType("nebulizer", "네뷸라이저 작동음", nebulizer, 15, 60, 0.5, False),
    "crowd_babble": NoiseType("crowd_babble", "붐비는 사람 소리 (회진·대화)", crowd_babble, 10, 40, 0.5, False),
    "footsteps": NoiseType("footsteps", "복도 발소리", footsteps, 3, 10, 0.3, False),
    "cart_rolling": NoiseType("cart_rolling", "카트/침대 바퀴 소리", cart_rolling, 4, 10, 0.4, False),
    "door": NoiseType("door", "문 여닫는 소리", door, 0.8, 1.0, 0.5, False),
    "phone_ring": NoiseType("phone_ring", "전화벨", phone_ring, 3, 9, 0.35, False),
    "keyboard": NoiseType("keyboard", "키보드 타이핑", keyboard, 4, 15, 0.25, False),
    "curtain": NoiseType("curtain", "커튼 소리", curtain, 1, 2, 0.4, False),
}


def render(key: str, dur: float, sr: int, rng: np.random.Generator, n: int | None = None) -> np.ndarray:
    """Render ``key`` for ``dur`` seconds (exactly ``n`` samples when given), peak-normalised to <= 1."""
    nt = BUILTIN[key]
    out = nt.fn(dur, sr, rng).astype(np.float32)
    peak = float(np.max(np.abs(out))) if out.size else 0.0
    if peak > 1.0:
        out = out / peak
    if n is not None:
        if len(out) < n:
            out = np.concatenate([out, np.zeros(n - len(out), dtype=np.float32)])
        else:
            out = out[:n]
    return out
