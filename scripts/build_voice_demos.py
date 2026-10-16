#!/usr/bin/env python3
"""등록된 목소리마다 고정 문장 데모(약 10초)를 합성해 번들 자산(backend/nursing_tts/assets/voice_demos)에 넣는다.

앱은 목소리를 고를 때 원음이 아니라 이 데모를 들려준다. 번들에 있으면 다른 PC에 설치해도 합성 없이 바로 들린다
(목소리 id 기준이므로 voices/ 폴더를 그대로 옮긴 경우). 백엔드(기본 http://127.0.0.1:8766)가 떠 있어야 하고,
데모가 아직 없는 목소리는 그 자리에서 합성한다(모델이 내려가 있으면 첫 목소리에 수 분).

  backend/.venv/bin/python scripts/build_voice_demos.py            # 샘플이 있는 모든 목소리
  backend/.venv/bin/python scripts/build_voice_demos.py --voice 간호사   # 이름에 포함된 것만
  backend/.venv/bin/python scripts/build_voice_demos.py --force    # 이미 번들에 있어도 다시
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from nursing_tts.voices import ASSET_DEMOS, DEMO_TEXT  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8766")
    ap.add_argument("--voice", default="", help="이름에 이 문자열이 포함된 목소리만")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    ASSET_DEMOS.mkdir(parents=True, exist_ok=True)
    manifest_path = ASSET_DEMOS / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    voices = json.load(urllib.request.urlopen(a.api + "/api/voices"))
    for v in voices:
        if a.voice not in v["name"] or not v["samples"]:
            continue
        out = ASSET_DEMOS / f"{v['id']}.flac"
        if out.exists() and not a.force:
            print(f"  = {v['name']} ({v['id']}) 이미 있음")
            continue
        t0 = time.time()
        if a.force:
            out.unlink(missing_ok=True)   # the endpoint prefers the bundled file, so remove it first
        wav = urllib.request.urlopen(f"{a.api}/api/voices/{v['id']}/demo", timeout=900).read()
        audio, sr = sf.read(io.BytesIO(wav), dtype="float32")
        sf.write(out, audio, sr, format="FLAC")
        manifest[v["id"]] = {"name": v["name"], "sex": v.get("sex", ""), "note": v.get("note", ""), "text": DEMO_TEXT,
                             "seconds": round(len(audio) / sr, 1), "built": time.strftime("%Y-%m-%d")}
        print(f"  + {v['name']} ({v['id']}) {len(audio) / sr:.1f}초, {time.time() - t0:.0f}초 걸림")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"번들 데모 {len(manifest)}개 → {ASSET_DEMOS}")


if __name__ == "__main__":
    main()
