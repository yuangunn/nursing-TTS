"""Doctor-rounds background chatter.

The real "회진" sound in a ward is a conversation two beds away: a doctor asking, the patient
answering, a nurse reporting.  We script a short exchange, read every line with the registered
nurse voice (clone engine), then shift pitch and tempo per role so it sounds like a middle-aged
man, an older woman and another nurse, and push it far away (band-pass + room) with the mixer's
extra-voice treatment.  Without a clone engine the OS voice is used instead.  Saved as a user
noise clip.  Per-role pitch/tempo live in settings (``rounds_shift``, ``rounds_tempo``).
"""
from __future__ import annotations

import random
from pathlib import Path

import numpy as np

from .audio.augment import speed_perturb
from .audio.mixer import _distant
from .tts.base import natural_pause, trim_silence

DOCTOR = [
    "어제보다 많이 좋아지셨네요. 가스 나오면 물부터 조금씩 드셔 보세요.",
    "통증은 어떠세요? 걷는 게 제일 중요해요. 하루 다섯 바퀴 이상 걸으세요.",
    "검사 결과는 괜찮습니다. 드레싱은 내일 소독하고 실밥은 외래에서 뽑을게요.",
    "식사는 잘 드세요? 그러면 내일부터 죽으로 올리겠습니다.",
    "열이 좀 있으셨죠. 심호흡 열심히 하시고 폐활량계 자주 하세요.",
    "오늘 피검사 한 번 더 나가고, 괜찮으면 모레쯤 퇴원 얘기해 봅시다.",
    "배액관은 양이 줄면 내일 빼겠습니다. 불편한 거 있으세요?",
]
PATIENT = [
    "네, 어제보다는 좀 나아요. 밤에 한 번 깼어요.",
    "걸을 때 당기는데 참을 만해요.",
    "밥은 반 정도 먹었어요. 속이 좀 더부룩해요.",
    "네, 알겠습니다. 감사합니다.",
    "소변은 잘 나오는데 가스는 아직이에요.",
    "열은 지금은 없는 것 같아요.",
]
NURSE = [
    "어젯밤 체온 삼십칠 점 사까지 올랐다가 지금은 정상이고요, 진통제 한 번 들어갔습니다.",
    "배액 양은 어제 육십, 오늘 삼십이고 색은 옅어졌습니다.",
    "혈당 식전 백오십이라 슬라이딩 유지 중입니다.",
    "수액 하트만 유지 중이고 소변량 괜찮습니다.",
    "오늘 복도 세 바퀴 걸으셨고 통증 삼 점입니다.",
]

# Defaults (settings override): pitch in semitones from the registered voice, tempo 1.0 = its own pace.
ROLE_SHIFT = {"doctor": -4.0, "patient": -1.0, "nurse": 3.0}
ROLE_TEMPO = {"doctor": 1.05, "patient": 0.9, "nurse": 1.15}
# OS-voice fallback: only tempo/pitch via resampling tells the speakers apart.
_SPEED = {"doctor": 0.9, "patient": 1.1, "nurse": 1.0}


def make_dialogue(rng: random.Random, turns: int = 6) -> list[tuple[str, str]]:
    """[(role, line)] - doctor opens, patient/nurse alternate."""
    out = [("doctor", rng.choice(DOCTOR))]
    for i in range(turns - 1):
        role = "patient" if i % 2 == 0 else rng.choice(["nurse", "doctor", "patient"])
        pool = {"doctor": DOCTOR, "patient": PATIENT, "nurse": NURSE}[role]
        out.append((role, rng.choice(pool)))
    return out


def pitch_shift(audio: np.ndarray, sr: int, semitones: float) -> np.ndarray:
    """Pitch without tempo change (librosa comes with qwen-tts); plain resampling as a fallback."""
    if abs(semitones) < 0.01:
        return audio
    try:
        import librosa  # type: ignore

        return librosa.effects.pitch_shift(audio.astype(np.float32), sr=sr, n_steps=semitones).astype(np.float32)
    except ImportError:
        # ponytail: fallback also changes tempo; good enough for far-away chatter
        return speed_perturb(audio, 2 ** (semitones / 12))


def time_stretch(audio: np.ndarray, rate: float) -> np.ndarray:
    """Tempo without pitch change (rate > 1 = faster); resampling fallback changes pitch too."""
    if abs(rate - 1.0) < 0.01:
        return audio
    try:
        import librosa  # type: ignore

        return librosa.effects.time_stretch(audio.astype(np.float32), rate=rate).astype(np.float32)
    except ImportError:
        return speed_perturb(audio, rate)


def render(engine, rng: random.Random, sr: int = 24000, turns: int = 6,
           ref: tuple[Path, str] | None = None, shift: dict | None = None, tempo: dict | None = None,
           jitter: float = 0.08) -> tuple[np.ndarray, list[tuple[str, str]]]:
    """Render a rounds conversation as far-away chatter. Returns (audio, dialogue).

    ``ref`` = (sample path, transcript) of a registered voice for a cloning engine; None = OS voice.
    ``shift``/``tempo`` map role -> semitones / tempo factor; each line also gets +-``jitter`` tempo."""
    shift = {**ROLE_SHIFT, **(shift or {})}
    tempo = {**ROLE_TEMPO, **(tempo or {})}
    dialogue = make_dialogue(rng, turns)
    pieces: list[np.ndarray] = []
    for role, line in dialogue:
        audio, asr = engine.synthesize(line, ref, seed=rng.randrange(1 << 30))
        if asr != sr:
            from .audio.io import resample
            audio = resample(audio, asr, sr)
        audio = trim_silence(audio.astype(np.float32), sr)
        if ref is not None:
            audio = pitch_shift(audio, sr, float(shift[role]))
            audio = time_stretch(audio, float(tempo[role]) * (1 + rng.uniform(-jitter, jitter)))
        else:
            audio = speed_perturb(audio, _SPEED[role])
        pieces.append(audio)
        pieces.append(np.zeros(int(natural_pause(rng) * sr), dtype=np.float32))
    joined = np.concatenate(pieces[:-1]) if pieces else np.zeros(sr, dtype=np.float32)
    far = _distant(joined, sr, np.random.default_rng(rng.randrange(1 << 30)))
    return (far * 0.9).astype(np.float32), dialogue
