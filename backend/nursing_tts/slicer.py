"""Slice a long recording into short voice-enrollment clips.

Real nurses hand us 2-3 minute narrations; cloning models want 6-14 s
references.  We cut on silence (energy VAD), merge to the target length and,
when faster-whisper is installed, transcribe each clip so it can be used as a
reference with its text.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .audio.io import normalize_peak, read_audio, write_wav


@dataclass
class Clip:
    start: float
    end: float
    audio: np.ndarray
    transcript: str = ""


def _voiced_mask(audio: np.ndarray, sr: int, frame: float = 0.03) -> tuple[np.ndarray, int]:
    n = int(frame * sr)
    count = len(audio) // n
    if count == 0:
        return np.array([True]), n
    e = np.sqrt(np.mean(audio[: count * n].reshape(count, n) ** 2, axis=1))
    floor = np.percentile(e, 15)
    loud = np.percentile(e, 95)
    # 3x the noise floor, but never above ~12% of the loud level (recordings with little silence)
    thr = max(1e-4, min(floor * 3.0, loud * 0.12))
    return e > thr, n


def slice_recording(audio: np.ndarray, sr: int, min_len: float = 6.0, target_len: float = 10.0, max_len: float = 14.0,
                    min_gap: float = 0.35, pad: float = 0.15) -> list[Clip]:
    voiced, n = _voiced_mask(audio, sr)
    # speech segments between pauses >= min_gap
    segs: list[tuple[int, int]] = []
    i = 0
    gap_frames = int(min_gap / (n / sr))
    cur_start = None
    silent_run = 0
    for i, v in enumerate(voiced):
        if v:
            if cur_start is None:
                cur_start = i
            silent_run = 0
        else:
            silent_run += 1
            if cur_start is not None and silent_run >= gap_frames:
                segs.append((cur_start, i - silent_run + 1))
                cur_start = None
    if cur_start is not None:
        segs.append((cur_start, len(voiced)))
    # merge consecutive segments up to target/max length
    clips: list[Clip] = []
    acc_start = None
    acc_end = None
    for s, e in segs:
        if acc_start is None:
            acc_start, acc_end = s, e
            continue
        if (e - acc_start) * n / sr <= max_len and (acc_end - acc_start) * n / sr < target_len:
            acc_end = e
        else:
            clips.append(_mk(audio, sr, acc_start, acc_end, n, pad))
            acc_start, acc_end = s, e
    if acc_start is not None:
        clips.append(_mk(audio, sr, acc_start, acc_end, n, pad))
    out = [c for c in clips if (c.end - c.start) >= min_len]
    # long leftover (no pauses): hard split
    final: list[Clip] = []
    for c in out:
        if c.end - c.start > max_len * 1.5:
            k = int(np.ceil((c.end - c.start) / target_len))
            step = len(c.audio) // k
            for j in range(k):
                a = c.audio[j * step:(j + 1) * step]
                if len(a) / sr >= min_len:
                    final.append(Clip(c.start + j * step / sr, c.start + (j + 1) * step / sr, a))
        else:
            final.append(c)
    return final


def _mk(audio: np.ndarray, sr: int, s: int, e: int, n: int, pad: float) -> Clip:
    a = max(0, s * n - int(pad * sr))
    b = min(len(audio), e * n + int(pad * sr))
    return Clip(a / sr, b / sr, audio[a:b])


def process(path: Path, sr: int = 24000, transcribe: bool = True, max_clips: int = 12,
            model_size: str = "small", device: str = "auto") -> list[Clip]:
    audio, _ = read_audio(path, sr)
    audio = normalize_peak(audio, 0.9)
    clips = slice_recording(audio, sr)
    # prefer clips closest to 10 s
    clips.sort(key=lambda c: abs((c.end - c.start) - 10.0))
    clips = sorted(clips[:max_clips], key=lambda c: c.start)
    if transcribe:
        try:
            from . import verify as verify_mod
            ok, _ = verify_mod.available()
            if ok:
                model = verify_mod._load(model_size, device)
                from .audio.io import resample
                for c in clips:
                    a16 = resample(c.audio, sr, 16000)
                    segs, _ = model.transcribe(a16, language="ko", beam_size=5, vad_filter=False)
                    c.transcript = " ".join(s.text.strip() for s in segs)
        except Exception:  # noqa: BLE001
            pass
    return clips
