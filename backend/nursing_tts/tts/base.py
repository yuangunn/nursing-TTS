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


def trim_silence(audio: np.ndarray, sr: int, threshold: float = 0.002, keep: float = 0.18, fade: float = 0.03) -> np.ndarray:
    """Cut the model's own leading/trailing silence so the pause between chunks is ours alone
    (Qwen sometimes appends 2-3 s of silence; combined with our pause that gave 7 s gaps).

    Keeps ``keep`` seconds around the last audible frame so the natural decay/breath at a sentence
    end survives, and fades the edges so the cut never sounds abrupt (user feedback: "뚝 끊김")."""
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
    out = audio[a:b].copy()
    f = min(int(fade * sr), len(out) // 4)
    if f > 0:
        ramp = np.linspace(0, 1, f, dtype=np.float32)
        out[:f] *= ramp
        out[-f:] *= ramp[::-1]
    return out


def natural_pause(rng: random.Random, scale: float = 1.0) -> float:
    """Pause length in seconds. Log-normal fitted to three real nurse dictations (2026-10-15):
    median 0.6 s, p90 1.6 s, a few 2-4 s; section changes (scale ~1.6) run longer."""
    return min(3.5, max(0.25, rng.lognormvariate(math.log(0.6 * scale), 0.75)))


def plan_chunks(spoken_lines: list[str], tts_lines: list[str], min_chars: int = 20) -> list[tuple[int, str, str, bool]]:
    """Pair each phonetic chunk with its ground-truth text: (paragraph index, spoken, tts, last in paragraph).

    Both layers split on the same sentence boundaries; when a paragraph's sentence counts disagree
    (rare: a conversion that added/removed a period) the whole paragraph becomes one chunk."""
    plan: list[tuple[int, str, str, bool]] = []
    for i, (sp, tt) in enumerate(zip(spoken_lines, tts_lines)):
        s_sents = [s for s in _SENT_SPLIT.split(sp.strip()) if s.strip()]
        t_sents = [s for s in _SENT_SPLIT.split(tt.strip()) if s.strip()]
        if len(s_sents) != len(t_sents) or not t_sents:
            plan.append((i, sp.strip(), tt.strip(), True))
            continue
        pairs: list[list[str]] = []
        for s, t in zip(s_sents, t_sents):
            if pairs and len(re.sub(r"\s", "", pairs[-1][1])) < min_chars:
                pairs[-1] = [f"{pairs[-1][0]} {s}", f"{pairs[-1][1]} {t}"]
            else:
                pairs.append([s, t])
        if len(pairs) > 1 and len(re.sub(r"\s", "", pairs[-1][1])) < min_chars:
            last = pairs.pop()
            pairs[-1] = [f"{pairs[-1][0]} {last[0]}", f"{pairs[-1][1]} {last[1]}"]
        for j, (s, t) in enumerate(pairs):
            plan.append((i, s, t, j == len(pairs) - 1))
    return plan


def _synth_all(engine: TTSEngine, texts: list[str], ref: tuple[Path, str] | None, seed: int | None,
               progress=None, total: int = 1, para_of: list[int] | None = None) -> tuple[list[np.ndarray], int]:
    many = getattr(engine, "synthesize_many", None)
    if many is not None:  # batched engines (Qwen): all chunks of the recording in a few generate calls
        audios, sr = many(texts, ref, seed)
        if progress:
            progress(total, total)
        return list(audios), sr
    audios, sr = [], 24000
    for k, text in enumerate(texts):
        audio, sr = engine.synthesize(text, ref, seed=(seed + k) if seed is not None else None)
        audios.append(audio)
        if progress:
            progress((para_of[k] if para_of else k) + 1, total)
    return audios, sr


def synthesize_script(engine: TTSEngine, spoken_lines: list[str], tts_lines: list[str], ref: tuple[Path, str] | None,
                      seed: int | None, progress=None, verify=None, cer_threshold: float = 0.3,
                      retries: int = 2) -> tuple[np.ndarray, int, list[dict]]:
    """Synthesize sentence chunks and join them with natural pauses.

    Returns (audio, sr, segments) where each segment is {start, end, text, tts[, cer, retries]} in
    seconds of the returned audio: exact labels for splitting long recordings into ≤30 s clips.
    Pauses between sentences follow the real-recording distribution; paragraph (section) changes get
    longer ones.  Synthesizing per sentence also gives the model shorter inputs.

    ``verify(spoken, tts, audio, sr) -> cer`` (e.g. Whisper read-back) turns this into a repair loop:
    chunks whose CER exceeds ``cer_threshold`` are re-synthesized with new seeds up to ``retries``
    times and the best take is kept."""
    rng = random.Random(seed)
    sr = 24000
    total = len(tts_lines)
    plan = plan_chunks(spoken_lines, tts_lines)
    if not plan:
        return np.zeros(int(0.5 * sr), dtype=np.float32), sr, []
    texts = [t for _, _, t, _ in plan]
    audios, sr = _synth_all(engine, texts, ref, seed, progress, total, [i for i, _, _, _ in plan])
    audios = [trim_silence(np.asarray(a, dtype=np.float32), sr) for a in audios]
    cers: list[float | None] = [None] * len(plan)
    tries: list[int] = [0] * len(plan)
    if verify is not None:
        cers = [float(verify(spoken, tts, a, sr)) for (_, spoken, tts, _), a in zip(plan, audios)]
        for attempt in range(1, retries + 1):
            bad = [k for k, c in enumerate(cers) if c is not None and c > cer_threshold]
            if not bad:
                break
            new_audios, _ = _synth_all(engine, [texts[k] for k in bad], ref, (seed + 1000 * attempt) if seed is not None else None)
            for k, a in zip(bad, new_audios):
                a = trim_silence(np.asarray(a, dtype=np.float32), sr)
                c = float(verify(plan[k][1], plan[k][2], a, sr))
                tries[k] = attempt
                if c < cers[k]:  # keep the better take
                    cers[k], audios[k] = c, a
    pieces: list[np.ndarray] = []
    segments: list[dict] = []
    pos = 0
    for k, ((i, spoken, tts, last_chunk), a) in enumerate(zip(plan, audios)):
        pieces.append(a)
        seg = {"start": round(pos / sr, 3), "end": round((pos + len(a)) / sr, 3), "text": spoken, "tts": tts}
        if cers[k] is not None:
            seg["cer"] = round(cers[k], 4)
            seg["retries"] = tries[k]
        segments.append(seg)
        pos += len(a)
        if not (last_chunk and i == total - 1):
            pause = int(natural_pause(rng, 1.6 if last_chunk else 1.0) * sr)
            pieces.append(np.zeros(pause, dtype=np.float32))
            pos += pause
    return np.concatenate(pieces), sr, segments


def synthesize_paragraphs(engine: TTSEngine, paragraphs: list[str], ref: tuple[Path, str] | None,
                          seed: int | None, progress=None) -> tuple[np.ndarray, int]:
    """Phonetic-only convenience wrapper around :func:`synthesize_script`."""
    audio, sr, _ = synthesize_script(engine, paragraphs, paragraphs, ref, seed, progress)
    return audio, sr
