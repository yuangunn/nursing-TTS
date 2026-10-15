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


def synthesize_script(engine: TTSEngine, spoken_lines: list[str], tts_lines: list[str], ref: tuple[Path, str] | None,
                      seed: int | None, progress=None) -> tuple[np.ndarray, int, list[dict]]:
    """Synthesize sentence chunks and join them with natural pauses.

    Returns (audio, sr, segments) where each segment is {start, end, text, tts} in seconds of the
    returned audio: exact labels for splitting long recordings into ≤30 s training clips.
    Pauses between sentences follow the real-recording distribution; paragraph (section) changes get
    longer ones.  Synthesizing per sentence also gives the model shorter inputs."""
    rng = random.Random(seed)
    sr = 24000
    total = len(tts_lines)
    plan = plan_chunks(spoken_lines, tts_lines)
    if not plan:
        return np.zeros(int(0.5 * sr), dtype=np.float32), sr, []
    texts = [t for _, _, t, _ in plan]
    many = getattr(engine, "synthesize_many", None)
    if many is not None:  # batched engines (Qwen): all chunks of the recording in a few generate calls
        audios, sr = many(texts, ref, seed)
        if progress:
            progress(total, total)
    else:
        audios = []
        for k, text in enumerate(texts):
            audio, sr = engine.synthesize(text, ref, seed=(seed + k) if seed is not None else None)
            audios.append(audio)
            if progress:
                progress(plan[k][0] + 1, total)
    pieces: list[np.ndarray] = []
    segments: list[dict] = []
    pos = 0
    for (i, spoken, tts, last_chunk), audio in zip(plan, audios):
        a = trim_silence(np.asarray(audio, dtype=np.float32), sr)
        pieces.append(a)
        segments.append({"start": round(pos / sr, 3), "end": round((pos + len(a)) / sr, 3), "text": spoken, "tts": tts})
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
