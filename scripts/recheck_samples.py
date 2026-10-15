#!/usr/bin/env python3
"""등록된 목소리 샘플의 전사를 더 큰 Whisper로 다시 받아 비교하고, 원하면 바꿔 넣는다.

복제 엔진은 참조 샘플의 전사(ref_text)를 그대로 믿으므로, 자동 전사(small)의 오류("트윈스타"→"트윤스타",
"활력징후"→"활력 증후")가 복제 말투에 섞인다. medium/large-v3로 다시 받아 차이를 보여 준다.

  backend/.venv/bin/python scripts/recheck_samples.py                 # 비교만 (medium)
  backend/.venv/bin/python scripts/recheck_samples.py --apply         # CER 차이가 큰 것만 교체
  backend/.venv/bin/python scripts/recheck_samples.py --model large-v3 --voice 간호사8

백엔드(기본 http://127.0.0.1:8766)가 떠 있어야 한다. 교체 전 전사는 local_data/sample_transcripts_backup.json에 남긴다.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from nursing_tts.verify import cer, transcribe  # noqa: E402
from nursing_tts.config import data_dir  # noqa: E402


def call(api: str, path: str, body=None, method=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(api + path, data=data, headers={"content-type": "application/json"}, method=method)
    return json.load(urllib.request.urlopen(req))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8766")
    ap.add_argument("--model", default="medium", help="faster-whisper 모델 (medium, large-v3 ...)")
    ap.add_argument("--voice", default="", help="이름에 이 문자열이 포함된 목소리만")
    ap.add_argument("--apply", action="store_true", help="CER 차이가 --min-diff 이상인 샘플의 전사를 교체")
    ap.add_argument("--min-diff", type=float, default=0.08)
    a = ap.parse_args()

    voices = [v for v in call(a.api, "/api/voices") if a.voice in v["name"]]
    backup_path = ROOT / "backend" / "local_data" / "sample_transcripts_backup.json"
    backup = json.loads(backup_path.read_text(encoding="utf-8")) if backup_path.exists() else {}
    changed = 0
    t0 = time.time()
    for v in voices:
        print(f"== {v['name']} ({len(v['samples'])}개)")
        for smp in v["samples"]:
            wav = data_dir() / "voices" / v["id"] / smp["file"]
            if not wav.exists():
                wav = data_dir() / "voices" / smp["file"]
            if not wav.exists():
                print(f"   {smp['id']}: 파일 없음 {smp['file']}")
                continue
            old = smp.get("transcript", "")
            new = transcribe(wav, a.model, "auto")
            d = cer(old, new) if old else 1.0
            flag = "≠" if d >= a.min_diff else " "
            print(f" {flag} {smp['id']} CER(old→new)={d:.2f}\n     old: {old[:100]}\n     new: {new[:100]}")
            if a.apply and d >= a.min_diff and new.strip():
                backup.setdefault(v["id"], {})[smp["id"]] = old
                call(a.api, f"/api/voices/{v['id']}/samples/{smp['id']}", {"transcript": new}, method="PATCH")
                changed += 1
    if a.apply:
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_text(json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"교체 {changed}개, 예전 전사는 {backup_path}")
    print(f"{time.time() - t0:.0f}초")


if __name__ == "__main__":
    main()
