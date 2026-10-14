"""Doctor-rounds background chatter rendered with the OS TTS.

The real "회진" sound in a ward is a conversation two beds away: a doctor asking, the patient
answering, a nurse reporting.  Instead of recording one we script a short exchange, read it
with the system voice (macOS say / Windows SAPI) and push it far away (band-pass + room) with
the same treatment the mixer uses for extra voices.  The result is saved as a user noise clip.
"""
from __future__ import annotations

import random

import numpy as np

from .audio.augment import speed_perturb
from .audio.mixer import _distant
from .tts.base import natural_pause

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


def make_dialogue(rng: random.Random, turns: int = 6) -> list[tuple[str, str]]:
    """[(role, line)] - doctor opens, patient/nurse alternate."""
    out = [("doctor", rng.choice(DOCTOR))]
    for i in range(turns - 1):
        role = "patient" if i % 2 == 0 else rng.choice(["nurse", "doctor", "patient"])
        pool = {"doctor": DOCTOR, "patient": PATIENT, "nurse": NURSE}[role]
        out.append((role, rng.choice(pool)))
    return out


# ponytail: one system voice for everyone; speed/pitch shift tells the speakers apart well enough at a distance.
_SPEED = {"doctor": 0.9, "patient": 1.1, "nurse": 1.0}


def render(engine, rng: random.Random, sr: int = 24000, turns: int = 6) -> tuple[np.ndarray, list[tuple[str, str]]]:
    """Render a rounds conversation as far-away chatter. Returns (audio, dialogue)."""
    dialogue = make_dialogue(rng, turns)
    pieces: list[np.ndarray] = []
    for role, line in dialogue:
        audio, asr = engine.synthesize(line, None, seed=rng.randrange(1 << 30))
        if asr != sr:
            from .audio.io import resample
            audio = resample(audio, asr, sr)
        pieces.append(speed_perturb(audio.astype(np.float32), _SPEED[role]))
        pieces.append(np.zeros(int(natural_pause(rng) * sr), dtype=np.float32))
    joined = np.concatenate(pieces[:-1]) if pieces else np.zeros(sr, dtype=np.float32)
    far = _distant(joined, sr, np.random.default_rng(rng.randrange(1 << 30)))
    return (far * 0.9).astype(np.float32), dialogue
