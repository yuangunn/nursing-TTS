#!/usr/bin/env python3
"""블라인드 청취 세트 만들기 (ROADMAP M2 완료 기준용).

실제 녹음과 생성물에서 같은 길이의 구간을 잘라 무작위 이름(A, B, C…)으로 섞어 저장하고,
정답표(key.json)는 따로 둔다. 듣는 사람에게는 폴더의 wav만 준다.

  python scripts/blind_set.py --real backend/local_data/real --generated "<출력 폴더>" \
      --out backend/local_data/blind --n 10 --seconds 30

backend/.venv 로 실행 (soundfile 필요). 폴더는 gitignore(local_data) 안에 둔다.
"""
from __future__ import annotations

import argparse
import json
import random
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from nursing_tts.audio.io import read_audio, write_wav  # noqa: E402


def excerpt(path: Path, seconds: float, rng: random.Random, sr: int = 24000):
    audio, _ = read_audio(path, sr)
    n = int(seconds * sr)
    if len(audio) <= n:
        return audio
    # skip the first 5 s (signal line / recorder start) when there is room
    lo = min(int(5 * sr), len(audio) - n)
    start = rng.randrange(lo, len(audio) - n + 1)
    return audio[start:start + n]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", required=True, type=Path)
    ap.add_argument("--generated", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--n", type=int, default=10, help="총 개수 (절반은 실제, 절반은 생성)")
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    real = sorted(p for p in a.real.glob("*") if p.suffix.lower() in (".wav", ".m4a", ".mp3", ".flac"))
    gen = sorted(a.generated.rglob("*.wav"))
    if not real or not gen:
        sys.exit(f"실제 {len(real)}개 / 생성 {len(gen)}개: 둘 다 1개 이상 필요")
    half = a.n // 2
    picks = [("real", p) for p in (rng.sample(real, half) if len(real) >= half else [rng.choice(real) for _ in range(half)])]
    picks += [("generated", p) for p in (rng.sample(gen, a.n - half) if len(gen) >= a.n - half else [rng.choice(gen) for _ in range(a.n - half)])]
    rng.shuffle(picks)
    a.out.mkdir(parents=True, exist_ok=True)
    key = []
    for label, (kind, src) in zip(string.ascii_uppercase, picks):
        audio = excerpt(src, a.seconds, rng)
        write_wav(a.out / f"{label}.wav", audio, 24000)
        key.append({"clip": f"{label}.wav", "kind": kind, "source": str(src)})
    (a.out / "key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
    (a.out / "answer_sheet.txt").write_text(
        "각 클립이 실제 녹음(실)인지 합성(합)인지 적어 주세요.\n\n" + "\n".join(f"{k['clip']}:  실 / 합" for k in key) + "\n",
        encoding="utf-8")
    print(f"{len(key)}개 → {a.out}  (정답: key.json, 답안지: answer_sheet.txt)")


if __name__ == "__main__":
    main()
