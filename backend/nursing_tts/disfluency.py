"""Spoken-language disfluencies: fillers, repetitions and self-corrections.

Real ward dictation is not clean prose.  A nurse pauses ("음…"), restarts a
phrase, or corrects a number ("37.4, 아니 37.1").  Applying a small amount of
this to the TTS input makes the audio closer to field recordings.  The clean
transcript is always kept; whether fillers also appear in the ground-truth
text is a per-export choice (``include_fillers``).
"""
from __future__ import annotations

import random
import re

# Weights follow three real nurse recordings (2026-10-15): read-aloud charting had ~0 fillers,
# interview-style 간호정보조사 ~2/min, mostly hedges (혹시·뭐·이제·좀) rather than 어/음.
FILLERS = ["어", "음", "그", "어 그", "자", "네", "이제", "뭐", "혹시", "혹시 뭐"]
FILLER_WEIGHTS = [4, 3, 3, 1, 1, 1, 3, 2, 2, 1]
TAIL_PAUSES = ["… ", ", "]
CORRECTION_WORDS = ["아니", "아 아니", "아니다", "아니고"]

_NUM_RE = re.compile(r"(?<![\d.])(\d{2,3}(?:\.\d)?)(?![\d.])")
_TIME_RE = re.compile(r"(오전|오후) (\d{1,2})시(?: (\d{1,2})분)?")
RESTATE_WORDS = ["정정하겠습니다", "아 정정하겠습니다", "다시 말씀드리면", "아니"]
_WORD_RE = re.compile(r"[가-힣A-Za-z]+")


def _perturb_number(tok: str, rng: random.Random) -> str:
    if "." in tok:
        whole, frac = tok.split(".")
        f = (int(frac) + rng.choice([-2, -1, 1, 2])) % 10
        return f"{whole}.{f}"
    n = int(tok)
    delta = rng.choice([-10, -5, -2, 2, 5, 10]) if n >= 50 else rng.choice([-2, -1, 1, 2])
    return str(max(1, n + delta))


def apply(text: str, level: int, rng: random.Random) -> tuple[str, list[dict]]:
    """level 0..3.  Returns (verbatim text, list of edits).  The first line (signal) is never touched."""
    if level <= 0 or not text.strip():
        return text, []
    lines = text.split("\n")
    out_lines = [lines[0]]
    edits: list[dict] = []
    p_filler = {1: 0.08, 2: 0.18, 3: 0.35}[min(level, 3)]
    p_repeat = {1: 0.02, 2: 0.05, 3: 0.10}[min(level, 3)]
    p_correct = {1: 0.03, 2: 0.07, 3: 0.14}[min(level, 3)]
    for li, line in enumerate(lines[1:], start=1):
        sentences = re.split(r"(?<=[.])\s+", line)
        new_sents = []
        for si, sent in enumerate(sentences):
            if not sent.strip():
                continue
            s = sent
            # self-correction on a number
            if rng.random() < p_correct:
                m = list(_NUM_RE.finditer(s))
                if m:
                    mm = rng.choice(m)
                    wrong = _perturb_number(mm.group(1), rng)
                    rep = f"{wrong}, {rng.choice(CORRECTION_WORDS)} {mm.group(1)}"
                    s = s[: mm.start()] + rep + s[mm.end():]
                    edits.append({"line": li, "type": "correction", "from": mm.group(1), "to": rep})
            # time self-correction ("오전 1시, 정정하겠습니다 오후 1시 30분")
            if rng.random() < p_correct * 0.6:
                tm = list(_TIME_RE.finditer(s))
                if tm:
                    mm = rng.choice(tm)
                    ampm = "오후" if mm.group(1) == "오전" else "오전"
                    wrong_variant = rng.choice([
                        f"{ampm} {mm.group(2)}시",                       # wrong am/pm
                        f"{mm.group(1)} {max(1, (int(mm.group(2)) + rng.choice([-1, 1]) - 1) % 12 + 1)}시",  # wrong hour
                    ])
                    rep = f"{wrong_variant}, {rng.choice(RESTATE_WORDS)} {mm.group(0)}"
                    s = s[: mm.start()] + rep + s[mm.end():]
                    edits.append({"line": li, "type": "time_correction", "from": mm.group(0), "to": rep})
            # word repetition / restart
            if rng.random() < p_repeat:
                words = s.split(" ")
                if len(words) > 3:
                    k = rng.randrange(0, len(words) - 2)
                    w = words[k]
                    if _WORD_RE.fullmatch(w) and len(w) >= 2:
                        words[k] = f"{w}, {w}"
                        s = " ".join(words)
                        edits.append({"line": li, "type": "repeat", "word": w})
            # filler at sentence start
            if rng.random() < p_filler:
                f = rng.choices(FILLERS, weights=FILLER_WEIGHTS)[0]
                s = f"{f}{rng.choice(TAIL_PAUSES)}{s}" if not s.startswith(f) else s
                edits.append({"line": li, "type": "filler", "word": f})
            new_sents.append(s)
        out_lines.append(" ".join(new_sents))
    return "\n".join(out_lines), edits


def strip_fillers(verbatim: str) -> str:
    """Best-effort removal of fillers inserted by :func:`apply` (used for clean transcripts)."""
    text = verbatim
    for f in sorted(FILLERS, key=len, reverse=True):
        text = re.sub(rf"(^|(?<=[.\n] ))(?:{re.escape(f)})(?:…|, )", r"\1", text, flags=re.M)
    return text
