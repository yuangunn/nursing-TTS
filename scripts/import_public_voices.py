#!/usr/bin/env python3
"""공개 한국어 음성 데이터의 화자를 목소리(참조 샘플)로 가져온다.

지원 데이터: Zeroth-Korean (CC BY 4.0, Lucas Jo · Wonkyum Lee, OpenSLR 40). Hugging Face 미러
`kresnik/zeroth_korean`의 datasets-server rows API에서 화자별로 6~12초짜리 낭독 문장 2~3개를 받아
앱 백엔드 API로 "공개 화자 Zeroth-<id>" 목소리를 만든다. 성별은 음성 기본주파수(F0)로 추정해
라벨만 붙인다(목소리 등록 화면에서 고칠 수 있음). 출처 표기는 목소리 메모와 내보내기 README에 남는다.

  backend/.venv/bin/python scripts/import_public_voices.py --count 20            # 화자 20명
  backend/.venv/bin/python scripts/import_public_voices.py --count 10 --sex 여  # 여성 추정 화자만
  backend/.venv/bin/python scripts/import_public_voices.py --list               # 화자 목록만

백엔드(기본 http://127.0.0.1:8766)가 떠 있어야 한다. 받은 클립은 CC BY 4.0이므로 데이터셋을 배포할
때 "Zeroth-Korean (CC BY 4.0)" 출처를 함께 적어야 한다.
"""
from __future__ import annotations

import argparse
import io
import json
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from nursing_tts.audio.io import resample  # noqa: E402

ROWS_API = "https://datasets-server.huggingface.co/rows"
DATASET = "kresnik/zeroth_korean"
ATTRIBUTION = "출처: Zeroth-Korean (CC BY 4.0, Lucas Jo·Wonkyum Lee, OpenSLR 40, HF kresnik/zeroth_korean)"
TOTAL_ROWS = 22263


def _get(url: str, retries: int = 5) -> bytes:
    last = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "nursing-tts-import"}), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:  # anonymous rate limit: back off hard
                wait = 60 * (i + 1)
                print(f"  rate limit, {wait}초 대기…", flush=True)
                time.sleep(wait)
            else:
                time.sleep(2 * (i + 1))
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"다운로드 실패 {url}: {last}")


def rows(offset: int, length: int = 100) -> list[dict]:
    q = urllib.parse.urlencode({"dataset": DATASET, "config": "default", "split": "train", "offset": offset, "length": length})
    data = json.loads(_get(f"{ROWS_API}?{q}"))
    return [r["row"] for r in data["rows"]]


def speaker_batches(step: int = 200, delay: float = 3.0):
    """Rows are grouped by speaker (≈200 rows each): one request every `step` rows meets a new speaker
    with ~100 of their sentences.  Yields (speaker_id, rows) lazily so `--count N` costs ~N requests."""
    seen: set[int] = set()
    for off in range(0, TOTAL_ROWS, step):
        by: dict[int, list[dict]] = {}
        for r in rows(off, 100):
            by.setdefault(int(r["speaker_id"]), []).append(r)
        for spk, rs in by.items():
            if spk not in seen:
                seen.add(spk)
                yield spk, rs
        time.sleep(delay)


def estimate_f0(audio: np.ndarray, sr: int) -> float:
    """Median F0 (Hz) by autocorrelation over voiced 40 ms frames; crude but enough for a sex label."""
    n = int(0.04 * sr)
    hop = n // 2
    lo, hi = int(sr / 400), int(sr / 70)
    f0s = []
    for i in range(0, len(audio) - n, hop):
        x = audio[i:i + n]
        if np.sqrt(np.mean(x ** 2)) < 0.02:
            continue
        x = x - np.mean(x)
        ac = np.correlate(x, x, mode="full")[n - 1:]
        if ac[0] <= 0:
            continue
        seg = ac[lo:hi]
        k = int(np.argmax(seg)) + lo
        if seg.max() / ac[0] > 0.3:
            f0s.append(sr / k)
    return float(np.median(f0s)) if f0s else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=10, help="가져올 화자 수")
    ap.add_argument("--sex", choices=["여", "남", "any"], default="any", help="F0 추정 성별로 거르기")
    ap.add_argument("--clips", type=int, default=2, help="화자당 샘플 수")
    ap.add_argument("--api", default="http://127.0.0.1:8766")
    ap.add_argument("--list", action="store_true", help="화자 목록만 출력")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--delay", type=float, default=3.0, help="rows API 요청 간격(초), 익명 한도 회피")
    a = ap.parse_args()
    rng = random.Random(a.seed)

    if a.list:
        for spk, rs in speaker_batches(delay=a.delay):
            print(f"  {spk}: 예) {rs[0]['text'][:40]}", flush=True)
        return

    existing = {v["name"] for v in json.loads(_get(f"{a.api}/api/voices"))}
    made = 0
    for spk, rs in speaker_batches(delay=a.delay):
        if made >= a.count:
            break
        name = f"공개 화자 Zeroth-{spk}"
        if name in existing:
            continue
        # pick candidates with longer sentences first (≈ longer audio), download and keep 5~13 s clips
        cands = sorted(rs, key=lambda r: -len(r["text"]))[:8]
        clips = []
        for r in cands:
            try:
                raw = _get(r["audio"][0]["src"])
                time.sleep(1.0)
                data, sr0 = sf.read(io.BytesIO(raw), dtype="float32", always_2d=True)
                audio, sr = resample(data.mean(axis=1), sr0, 24000), 24000
            except Exception as e:  # noqa: BLE001
                print(f"  {spk}: 클립 건너뜀 ({e})")
                continue
            dur = len(audio) / sr
            if 5.0 <= dur <= 13.0:
                clips.append((audio, sr, r["text"], dur))
            if len(clips) >= a.clips:
                break
        if not clips:
            continue
        f0 = estimate_f0(clips[0][0], clips[0][1])
        sex = "여" if f0 >= 160 else "남"
        if a.sex != "any" and sex != a.sex:
            continue
        body = json.dumps({"name": name, "sex": sex, "note": f"{ATTRIBUTION} · 화자 {spk} · F0 추정 {f0:.0f} Hz"}).encode()
        req = urllib.request.Request(f"{a.api}/api/voices", data=body, headers={"content-type": "application/json"})
        vid = json.load(urllib.request.urlopen(req))["id"]
        for audio, sr, text, dur in clips:
            buf = io.BytesIO()
            sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
            boundary = "----nursingtts"
            parts = [f"--{boundary}\r\nContent-Disposition: form-data; name=\"transcript\"\r\n\r\n{text}\r\n".encode(),
                     f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"zeroth_{spk}.wav\"\r\nContent-Type: audio/wav\r\n\r\n".encode()
                     + buf.getvalue() + b"\r\n", f"--{boundary}--\r\n".encode()]
            req = urllib.request.Request(f"{a.api}/api/voices/{vid}/samples", data=b"".join(parts),
                                         headers={"content-type": f"multipart/form-data; boundary={boundary}"})
            urllib.request.urlopen(req).read()
        made += 1
        print(f"  등록: {name} ({sex}, F0 {f0:.0f} Hz) · 클립 {len(clips)}개 · {', '.join(f'{d:.1f}s' for *_, d in clips)}", flush=True)
    print(f"완료: {made}명 등록. 데이터셋 배포 시 '{ATTRIBUTION}' 표기 필요")


if __name__ == "__main__":
    main()
