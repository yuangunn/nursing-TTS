#!/usr/bin/env python3
"""내보낸 데이터셋 폴더를 STT 학습 로더가 읽는 방식 그대로 검사한다 (ROADMAP M3).

  backend/.venv/bin/python scripts/check_export.py "<출력폴더>/_exports/<이름>"

검사: manifest·metadata·whisper jsonl·dataset.csv가 서로 같은 클립을 가리키는지, wav가 실제로 열리고
선언된 샘플레이트·mono·길이(±0.05초)와 맞는지, 전사가 비어 있지 않고 줄바꿈·파이프가 없는지,
split이 겹치지 않는지, 시그널 라벨(signal_end_char)이 전사 안에 있는지, 화자별 split 분포.
문제가 있으면 종료 코드 1. 마지막에 HF `datasets`로 읽는 예시 코드를 출력한다.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

try:
    import soundfile as sf
except ImportError:  # pragma: no cover
    sys.exit("soundfile 필요: backend/.venv/bin/python 으로 실행하세요")

root = Path(sys.argv[1]).expanduser()
report = json.loads((root / "report.json").read_text(encoding="utf-8"))
sr = int(report["sample_rate"])
problems: list[str] = []
seen_ids: dict[str, str] = {}
rows_by_split: dict[str, list[dict]] = {}

for part in ("train", "val", "test"):
    p = root / f"manifest_{part}.jsonl"
    if not p.exists():
        continue
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows_by_split[part] = rows
    for r in rows:
        f = root / r["audio_filepath"]
        rid = Path(r["audio_filepath"]).stem
        if rid in seen_ids:
            problems.append(f"{part}: {rid} 가 {seen_ids[rid]} 에도 있음 (split 겹침)")
        seen_ids[rid] = part
        if not f.exists():
            problems.append(f"{part}: 파일 없음 {r['audio_filepath']}")
            continue
        info = sf.info(str(f))
        if info.samplerate != sr or info.channels != 1 or info.subtype != "PCM_16":
            problems.append(f"{rid}: {info.samplerate} Hz / {info.channels}ch / {info.subtype} (기대 {sr} Hz mono PCM_16)")
        if abs(info.duration - float(r["duration"])) > 0.05:
            problems.append(f"{rid}: 길이 {info.duration:.2f}s ≠ manifest {r['duration']}")
        t = r["text"]
        if not t.strip() or "\n" in t or "|" in t:
            problems.append(f"{rid}: 전사 비었거나 줄바꿈/파이프 포함")
        st, end = r.get("signal_text") or "", int(r.get("signal_end_char") or 0)
        if st and not t.startswith(st):
            problems.append(f"{rid}: signal_text 가 전사 첫머리와 다름")
        if end > len(t):
            problems.append(f"{rid}: signal_end_char {end} > 전사 길이 {len(t)}")

# cross-check the other formats name the same clips
ids = set(seen_ids)
for name in ("metadata.csv",):
    p = root / name
    if p.exists():
        lj = {l.split("|")[0] for l in p.read_text(encoding="utf-8").splitlines() if l.strip()}
        if lj != ids:
            problems.append(f"{name}: 클립 집합이 manifest와 다름 (+{len(lj - ids)} / -{len(ids - lj)})")
for part in rows_by_split:
    p = root / f"whisper_{part}.jsonl"
    if p.exists():
        w = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        if {Path(x["audio"]).stem for x in w} != {Path(x["audio_filepath"]).stem for x in rows_by_split[part]}:
            problems.append(f"whisper_{part}.jsonl: 클립 집합이 manifest_{part}와 다름")
        if any(not x.get("sentence") or x.get("language") != "ko" for x in w):
            problems.append(f"whisper_{part}.jsonl: sentence 비었거나 language≠ko")
p = root / "dataset.csv"
if p.exists():
    with p.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if {r["id"] for r in rows} != ids:
        problems.append("dataset.csv: 클립 집합이 manifest와 다름")

total = sum(len(v) for v in rows_by_split.values())
print(f"{root.name}: {total}개, {sr} Hz, split " + " / ".join(f"{k} {len(v)}" for k, v in rows_by_split.items()))
spk = Counter((r.get("speaker"), part) for part, rs in rows_by_split.items() for r in rs)
for s in sorted({k[0] for k in spk}):
    print(f"  화자 {s}: " + ", ".join(f"{part} {spk[(s, part)]}" for part in rows_by_split if spk[(s, part)]))
dur = sum(float(r["duration"]) for rs in rows_by_split.values() for r in rs)
print(f"  총 {dur / 60:.1f}분, 평균 {dur / max(1, total):.1f}초/클립")
if problems:
    print(f"\n문제 {len(problems)}건:")
    for x in problems[:40]:
        print("  -", x)
    sys.exit(1)
print("\n문제 없음. HF datasets 로 읽는 예:")
print(f"""
  from datasets import load_dataset, Audio
  ds = load_dataset("json", data_files={{"train": "{root}/whisper_train.jsonl", "test": "{root}/whisper_test.jsonl"}})
  ds = ds.map(lambda x: {{"audio": "{root}/" + x["audio"]}}).cast_column("audio", Audio(sampling_rate={sr}))
  # ds["train"][0]["audio"]["array"], ds["train"][0]["sentence"]  -> WhisperProcessor 에 그대로
""")
