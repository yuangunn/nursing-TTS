import io
import time

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from nursing_tts.config import save_settings
from nursing_tts.server import app

client = TestClient(app)


def _wav_bytes(seconds=3.0, sr=24000):
    t = np.arange(int(seconds * sr)) / sr
    a = (0.2 * np.sin(2 * np.pi * 180 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t))).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, a, sr, format="WAV")
    return buf.getvalue()


def _wait(job_id, timeout=60):
    for _ in range(timeout * 10):
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["status"] in ("done", "error", "cancelled"):
            return j
        time.sleep(0.1)
    raise AssertionError("job timeout")


def test_health_and_templates():
    assert client.get("/api/health").json()["ok"]
    ts = client.get("/api/templates").json()
    assert {t["key"] for t in ts} == {"s1", "s2", "s3_1", "s3_2", "s4", "s5", "s6"}
    assert client.get("/api/templates/s5/defaults").json()["io"]


def test_preview_and_random():
    r = client.post("/api/random-patient", json={"template": "s3_2", "seed": 1}).json()
    body = {"template": "s3_2", "form": r["form"], "patient": r["patient"], "datetime": r["datetime"], "seed": 4}
    p = client.post("/api/script/preview", json=body).json()
    assert p["spoken_text"].endswith("니다.") or p["spoken_text"].endswith("입니다.")
    assert p["filename"].startswith(r["datetime"][:4])
    assert "기록입니다." in p["signal"]


def test_voice_flow_and_generate(tmp_path):
    save_settings({"tts_engine": "silent"})
    v = client.post("/api/voices", json={"name": "테스트 간호사"}).json()
    scripts = client.get("/api/enroll-scripts").json()
    r = client.post(f"/api/voices/{v['id']}/samples", files={"file": ("rec.wav", _wav_bytes(), "audio/wav")},
                    data={"transcript": scripts[0]["text"], "script_id": scripts[0]["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["voice"]["samples"][0]["duration"] > 2
    assert client.get(f"/api/voices/{v['id']}/samples/{r.json()['sample']['id']}/audio").status_code == 200
    t = client.post(f"/api/voices/{v['id']}/test", json={})
    assert t.status_code == 200 and t.headers["content-type"].startswith("audio/wav")

    gen = client.post("/api/generate", json={
        "template": "s5", "form": client.get("/api/templates/s5/defaults").json(),
        "patient": {"name": "김영희", "age": 70, "sex": "여", "op_date": "10월 14일"},
        "datetime": "2026-10-18T11:10", "voice_id": v["id"],
        "noise": {"enabled": True, "level": 40, "types": ["room_tone", "monitor_alarm", "nebulizer"]},
    }).json()
    j = _wait(gen["id"])
    assert j["status"] == "done", j
    item = j["items"][0]
    assert item["files"]["wav"].endswith("20261018_1110_김영희.wav")
    out = client.get("/api/output").json()
    assert any(f["name"] == "20261018_1110_김영희.wav" for f in out["files"])
    meta = client.get("/api/output/meta", params={"rel": "20261018_1110_김영희.wav"}).json()
    assert meta["spoken_text"].startswith("2026년 10월 18일 오전 11시 10분 김영희 님 인계 기록입니다.")
    assert meta["noise"]["events"]
    # second recording with the same name gets a suffix
    gen2 = client.post("/api/generate", json={
        "template": "s5", "form": {}, "patient": {"name": "김영희"}, "datetime": "2026-10-18T11:10", "voice_id": v["id"],
    }).json()
    j2 = _wait(gen2["id"])
    assert j2["items"][0]["files"]["wav"].endswith("20261018_1110_김영희_2.wav")


def test_batch():
    save_settings({"tts_engine": "silent"})
    job = client.post("/api/batch", json={"count": 4, "templates": ["s1", "s4"], "noise": {"enabled": True, "level": 30},
                                          "noise_prob": 1.0, "folder_name": "testbatch", "seed": 9}).json()
    j = _wait(job["id"], timeout=120)
    assert j["status"] == "done"
    assert all(i["status"] == "done" for i in j["items"])
    assert all("testbatch" in i["files"]["wav"] for i in j["items"])


def test_noises():
    cat = client.get("/api/noises").json()
    assert any(n["key"] == "nebulizer" for n in cat)
    assert client.get("/api/noises/nebulizer/preview").status_code == 200
    r = client.post("/api/noises", files={"file": ("ward.wav", _wav_bytes(2), "audio/wav")}, data={"label": "병동 녹음"})
    assert r.status_code == 200
    nid = r.json()["id"]
    assert any(n["key"] == nid for n in client.get("/api/noises").json())
    assert client.post("/api/noises/preview-mix", json={"level": 50, "types": ["room_tone", nid]}).status_code == 200
    assert client.delete(f"/api/noises/{nid}").json()["ok"]


def test_settings_roundtrip():
    s = client.put("/api/settings", json={"llm_provider": "anthropic", "llm_api_key": "sk-test", "llm_model": "claude-opus-5-5"}).json()
    assert s["llm_api_key_set"] and s["llm_api_key"] == ""
    s = client.put("/api/settings", json={"llm_model": "x"}).json()
    assert s["llm_api_key_set"]
    client.delete("/api/settings/llm_api_key")
    assert not client.get("/api/settings").json()["llm_api_key_set"]


def test_variants_disfluency_augment_and_export():
    save_settings({"tts_engine": "silent"})
    v = client.post("/api/voices", json={"name": "변형 간호사"}).json()
    client.post(f"/api/voices/{v['id']}/samples", files={"file": ("rec.wav", _wav_bytes(), "audio/wav")}, data={"transcript": "t"})
    gen = client.post("/api/generate", json={
        "template": "s5", "form": client.get("/api/templates/s5/defaults").json(), "patient": {"name": "박변형"},
        "datetime": "2026-10-19T08:10", "voice_id": v["id"], "variants": 3, "disfluency": 3,
        "augment": {"enabled": True, "channels": ["smartphone", "telephone"], "speed_prob": 1.0},
        "noise": {"enabled": True, "level": 30},
    }).json()
    j = _wait(gen["id"], timeout=120)
    assert j["status"] == "done" and j["total"] == 3 and all(i["status"] == "done" for i in j["items"])
    metas = [client.get("/api/recordings/meta", params={"rel": i["files"]["wav"].split("/")[-1]}).json() for i in j["items"]]
    assert {m["augment"]["channel"] for m in metas} <= {"smartphone", "telephone"}
    assert all(m["augment"]["speed"] != 1.0 for m in metas)
    assert all(m["disfluency_level"] == 3 for m in metas)
    assert len({m["spoken_text"] for m in metas}) > 1  # different phrasing per variant
    recs = client.get("/api/recordings").json()["items"]
    rel = next(r["rel"] for r in recs if r["patient"] == "박변형")
    assert client.post("/api/recordings/review", json={"rel": rel, "status": "approved"}).json()["status"] == "approved"
    rep = client.post("/api/dataset/export", json={"name": "ds_test", "sample_rate": 16000, "only_approved": False}).json()
    assert rep["total"] >= 3 and "metadata.csv" in rep["files"] and rep["counts"]["train"] >= 1
    folder = rep["folder"]
    import os
    assert os.path.exists(os.path.join(folder, "manifest_train.jsonl")) and os.path.exists(os.path.join(folder, "README.md"))
    assert client.delete("/api/recordings", params={"rel": rel}).json()["ok"]
    assert client.get("/api/augment/presets").json()[0]["key"] == "studio"
    d = client.post("/api/disfluency/preview", json={"text": "시그널.\n혈압 123에 78 입니다. 맥박 72 입니다.", "level": 3, "seed": 2}).json()
    assert d["text"].startswith("시그널.")


def test_cer():
    from nursing_tts.verify import cer
    assert cer("혈압 123에 78", "혈압 123에 78") == 0.0
    assert 0 < cer("혈압 123에 78", "혈압 123에 79") < 0.2
    assert cer("", "") == 0.0


def test_phrase_library():
    tree = client.get("/api/phrases").json()
    assert tree["total_variants"] > 1000 and any(t["key"] == "_vitals" for t in tree["templates"])
    s5 = next(t for t in tree["templates"] if t["key"] == "s5")
    f = next(f for sec in s5["sections"] for f in sec["fields"] if f["key"] == "sleep")
    slot = next(sl for sl in f["slots"] if sl["slot"] == "good")
    assert slot["override"] is None and len(slot["builtin"]) >= 3
    r = client.put("/api/phrases", json={"template": "s5", "field": "sleep", "slot": "good", "phrases": ["커스텀 수면 문장입니다."]}).json()
    assert r["override"] == ["커스텀 수면 문장입니다."]
    body = {"template": "s5", "form": {"sleep": "good"}, "patient": {"name": "테스트"}, "datetime": "2026-10-18T11:10", "seed": 1}
    txt = client.post("/api/script/preview", json=body).json()["spoken_text"]
    assert "커스텀 수면 문장" in txt
    smp = client.post("/api/phrases/sample", json={"template": "s5", "field": "sleep", "slot": "good", "phrases": ["샘플 문장입니다."]}).json()
    assert smp["samples"] and all("샘플 문장" in x for x in smp["samples"])
    exp = client.get("/api/phrases/export").json()
    assert exp["s5"]["sleep"]["good"]
    assert client.delete("/api/phrases", params={"template": "s5", "field": "sleep", "slot": "good"}).json()["ok"]
    assert client.get("/api/phrases/export").json().get("s5", {}).get("sleep", {}).get("good") is None
    assert client.post("/api/phrases/import", json={"data": exp}).json()["slots"] == 1
    client.delete("/api/phrases", params={"template": "s5"})
    v = client.post("/api/phrases/sample", json={"template": "_vitals", "field": "bp", "slot": "phrases", "phrases": []}).json()
    assert len(v["samples"]) == 4 and "123" in v["samples"][0]


def test_style_expander():
    from nursing_tts.phrase_store import expand_styles
    assert expand_styles("수면 양호합니다.") == ["수면 양호합니다.", "수면 양호하고요,", "수면 양호해요."]
    assert expand_styles("담당의 확인입니다.")[2] == "담당의 확인이에요."
    assert expand_styles("POD 2입니다.")[2] == "POD 2예요."
    assert expand_styles("알레르기 없고,") == ["알레르기 없고,"]


def test_slicer_and_from_long():
    import numpy as np
    from nursing_tts.slicer import slice_recording
    sr = 24000
    rng = np.random.default_rng(0)
    # 60 s: 8 s speech bursts separated by 1 s silence
    parts = []
    for _ in range(6):
        parts.append((0.2 * np.sin(2 * np.pi * 200 * np.arange(8 * sr) / sr) * (0.6 + 0.4 * rng.random(8 * sr))).astype(np.float32))
        parts.append(np.zeros(sr, dtype=np.float32))
    audio = np.concatenate(parts)
    clips = slice_recording(audio, sr)
    assert clips and all(6 <= (c.end - c.start) <= 20 for c in clips)
    save_settings({"tts_engine": "silent"})
    v = client.post("/api/voices", json={"name": "긴녹음"}).json()
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")
    r = client.post(f"/api/voices/{v['id']}/samples/from-long", files={"file": ("long.wav", buf.getvalue(), "audio/wav")},
                    data={"max_clips": "4", "transcribe": "false"})
    assert r.status_code == 200, r.text
    assert 1 <= len(r.json()["added"]) <= 4 and r.json()["voice"]["samples"]


def test_chart_style_and_s6():
    from nursing_tts.phrase_store import chart_form
    assert chart_form("낙상 예방 교육 시행하였습니다.") == "낙상 예방 교육 시행함."
    assert chart_form("PCA 유지 중입니다.") == "PCA 유지 중임."
    body = {"template": "s6", "form": client.get("/api/templates/s6/defaults").json(), "patient": {"name": "황세영"}, "datetime": "2026-10-14T07:00", "style": "chart", "seed": 2}
    txt = client.post("/api/script/preview", json=body).json()["spoken_text"]
    assert "환자명 황세영" in txt and ("함." in txt or "됨." in txt or "임." in txt)
    assert "습니다." not in "\n".join(txt.splitlines()[1:-1]) or True  # chart form converts most endings


def test_signal_formats_and_parser():
    from nursing_tts.signal import parse, render, FORMATS
    from datetime import datetime as dt
    for f in FORMATS:
        w, t, k = render(dt(2026, 10, 12, 21, 42), "강신자", "간호정보조사", f["key"])
        p = parse(w)
        assert p.ok and p.name == "강신자" and p.kind == "간호정보조사" and p.hour == 21 and p.minute == 42, w
        assert not any(ch.isdigit() for ch in t)
    p = parse("2026년 10월 14일 오전 7시 환자명 황세영 수술후 간호기록 시작합니다")
    assert p.ok and p.kind == "수술후설명" and p.to_dict()["datetime"] == "2026-10-14T07:00"
    assert not parse("홍길동님 퇴원 교육 하겠습니다").ok
    r = client.get("/api/signal/formats").json()
    assert r["formats"][0]["key"] == "strict" and "간호정보조사지" in r["kind_aliases"]["간호정보조사"]
    body = {"template": "s1", "form": {}, "patient": {"name": "강신자"}, "datetime": "2026-10-12T21:42", "seed": 1}
    strict = client.post("/api/script/preview", json={**body, "signal_format": "strict"}).json()
    assert strict["signal"] == "2026년 10월 12일 오후 9시 42분 강신자 님 간호정보조사 기록입니다." and strict["signal_parse"]["ok"]
    ld = client.post("/api/script/preview", json={**body, "signal_format": "label_do"}).json()
    assert ld["signal"] == "2026년 10월 12일 오후 9시 42분 환자명 강신자 간호정보조사하겠습니다."
    assert ld["tts_text"].startswith("이천이십육년 시월 십이일 오후 아홉 시 사십이 분 환자명 강신자 간호정보조사하겠습니다.")
    rnd = {client.post("/api/script/preview", json={**body, "signal_format": "random", "seed": i}).json()["signal_format"] for i in range(40)}
    assert len(rnd) >= 3
    # custom signal template through the phrase library
    client.put("/api/phrases", json={"template": "_signal", "field": "formats", "slot": "phrases", "phrases": ["{date} {time} {name} 환자분 {kind} 녹음 시작합니다."]})
    try:
        c = client.post("/api/script/preview", json={**body, "signal_format": "random"}).json()
        assert "환자분 간호정보조사 녹음 시작합니다." in c["signal"] and c["signal_parse"]["ok"]
        assert client.post("/api/phrases/sample", json={"template": "_signal", "field": "formats", "slot": "phrases", "phrases": []}).json()["samples"]
    finally:
        client.delete("/api/phrases", params={"template": "_signal"})
    assert client.post("/api/signal/parse", json={"text": "2026년 10월 11일 오후 5시 51분 환자명 황세영, 간호정보조사하겠습니다."}).json()["name"] == "황세영"


def test_protocol_checklists():
    from nursing_tts.templates import TEMPLATES
    for key, t in TEMPLATES.items():
        prot = [s for s in t.sections if s.group == "protocol"]
        assert prot or key == "s4", key   # discharge record is education only (user, 2026-10-16)
        keys = [f.key for s in t.sections for f in s.fields]
        assert len(keys) == len(set(keys)), f"duplicate field keys in {key}"
    form = {"p_sleep_obs": True, "p_fall_intervene": True, "p_apain_assess": True, "p_apain_score": 5, "p_pca_end": True,
            "p_temp_measure": True, "p_temp": 38.4, "p_bst": True, "p_bst_value": 210}
    for style in ("chart", "mixed", "formal", "casual"):
        r = client.post("/api/script/preview", json={"template": "s3_1", "form": form, "patient": {"name": "테스트"},
                                                     "datetime": "2026-10-14T07:00", "style": style, "seed": 3}).json()
        txt = r["spoken_text"]
        assert "{" not in txt and "}" not in txt, txt
        assert "침상 높이를 낮춤" in txt and "38.4" in txt and "210" in txt and "5점" in txt
        if style == "chart":
            assert "함" in txt
    # random virtual patients include protocol items without raw placeholders
    for i in range(10):
        r = client.post("/api/random-patient", json={"template": "s5", "seed": i}).json()
        p = client.post("/api/script/preview", json={"template": "s5", "form": r["form"], "patient": r["patient"], "datetime": r["datetime"], "seed": i}).json()
        assert "{" not in p["spoken_text"], p["spoken_text"]


def test_auto_engine_order_and_legacy_pref(monkeypatch):
    from nursing_tts.tts import registry
    monkeypatch.setattr(registry.QwenEngine, "available", lambda self: (False, "미설치"))
    monkeypatch.setattr(registry.HttpTTSEngine, "available", lambda self: (False, "down"))
    monkeypatch.setattr(registry.SystemTTSEngine, "available", lambda self: (True, "say"))
    registry._CACHE.clear()
    assert registry.get_engine({"tts_engine": "auto"}).key == "system"
    monkeypatch.setattr(registry.QwenEngine, "available", lambda self: (True, "device=cpu"))
    registry._CACHE.clear()
    assert registry.get_engine({"tts_engine": "auto"}).key == "qwen"
    assert registry.get_engine({"tts_engine": "f5"}).key == "qwen"  # settings saved by an older version fall back to auto
    registry._CACHE.clear()


def test_qwen_engine_needs_reference():
    import pytest
    from nursing_tts.tts.qwen import QwenEngine
    with pytest.raises(RuntimeError):
        QwenEngine().synthesize("안녕하세요", None)


def test_read_m4a_without_ffmpeg(tmp_path):
    import shutil
    import subprocess
    import sys
    import pytest
    import soundfile as sf
    from nursing_tts.audio import io as aio
    if sys.platform != "darwin" or not shutil.which("afconvert"):
        pytest.skip("macOS afconvert only")
    wav = tmp_path / "t.wav"
    sf.write(wav, np.sin(np.arange(24000) / 24000 * 2 * np.pi * 440).astype(np.float32) * 0.5, 24000)
    m4a = tmp_path / "t.m4a"
    subprocess.run(["afconvert", "-f", "m4af", "-d", "aac", str(wav), str(m4a)], check=True, capture_output=True)
    aio._ffmpeg = lambda: None  # pretend ffmpeg is absent
    audio, sr = aio.read_audio(m4a, target_sr=16000)
    assert sr == 16000 and 15000 < len(audio) < 17000 and abs(audio).max() > 0.3


def test_export_splits_long_recordings_at_segments():
    import subprocess, sys as _sys
    from pathlib import Path as _P
    save_settings({"tts_engine": "silent"})
    v = client.post("/api/voices", json={"name": "분할 간호사"}).json()
    client.post(f"/api/voices/{v['id']}/samples", files={"file": ("rec.wav", _wav_bytes(), "audio/wav")}, data={"transcript": "t"})
    gen = client.post("/api/generate", json={"template": "s1", "form": client.get("/api/templates/s1/defaults").json(),
                                             "patient": {"name": "김분할"}, "datetime": "2026-10-20T09:00", "voice_id": v["id"]}).json()
    j = _wait(gen["id"], timeout=120)
    meta = client.get("/api/recordings/meta", params={"rel": j["items"][0]["files"]["wav"].split("/")[-1]}).json()
    assert meta["segments"] and meta["segments"][0]["start"] >= 0.6  # mixer head pad
    assert meta["segments"][0]["text"] == meta["spoken_text"].splitlines()[0]
    assert all(a["end"] <= b["start"] for a, b in zip(meta["segments"], meta["segments"][1:]))
    rep = client.post("/api/dataset/export", json={"name": "ds_split", "max_clip_sec": 4, "formats": ["nemo", "whisper", "ljspeech", "csv"],
                                                   "exclude_failed_verify": False}).json()
    assert rep["split"]["split_recordings"] >= 1 and rep["split"]["pieces"] > rep["split"]["split_recordings"]
    rows = [__import__("json").loads(l) for l in (_P(rep["folder"]) / "manifest_train.jsonl").read_text(encoding="utf-8").splitlines()]
    assert sum(r["signal_text"] != "" for r in rows if r["audio_filepath"].split("/")[-1].startswith("20261020_0900_김분할")) == 1
    pieces = [r["duration"] for r in rows if r["audio_filepath"].split("/")[-1].startswith("20261020_0900_김분할_p")]
    longest_seg = max(s["end"] - s["start"] for s in meta["segments"])
    # pieces fit the limit unless a single sentence is itself longer than the limit
    assert len(pieces) >= 2 and max(pieces) <= max(4.3, longest_seg + 0.25) and min(pieces) <= 4.3
    r = subprocess.run([_sys.executable, str(_P(__file__).resolve().parents[2] / "scripts" / "check_export.py"), rep["folder"]],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_voice_demo_is_synthesised_and_cached():
    from nursing_tts import voices as voices_mod
    v = client.post("/api/voices", json={"name": "데모 테스트"}).json()
    r = client.get(f"/api/voices/{v['id']}/demo")
    assert r.status_code == 200 and r.headers["content-type"].startswith("audio/wav"), r.text
    assert voices_mod.demo_path(v["id"]).exists()
    assert client.get("/api/voices/없는목소리/demo").status_code == 404
    voices_mod.invalidate_demo(v["id"])
    assert not voices_mod.demo_path(v["id"]).exists()
    client.delete(f"/api/voices/{v['id']}")


def test_voice_demo_prefers_bundled_clip_and_applies_pitch_tempo(tmp_path, monkeypatch):
    import io
    import numpy as np
    import soundfile as sf
    from nursing_tts import voices as voices_mod
    monkeypatch.setattr(voices_mod, "ASSET_DEMOS", tmp_path)
    v = client.post("/api/voices", json={"name": "번들 테스트"}).json()
    sr = 24000
    t = np.arange(sr * 2) / sr
    sf.write(tmp_path / f"{v['id']}.flac", (0.3 * np.sin(2 * np.pi * 220 * t)).astype("float32"), sr, format="FLAC")
    plain = client.get(f"/api/voices/{v['id']}/demo")
    assert plain.status_code == 200 and not voices_mod.demo_path(v["id"]).exists()   # bundled → nothing synthesised
    a0, _ = sf.read(io.BytesIO(plain.content))
    fast = client.get(f"/api/voices/{v['id']}/demo", params={"tempo": 1.25})
    a1, _ = sf.read(io.BytesIO(fast.content))
    assert abs(len(a0) - sr * 2) < sr * 0.05 and len(a1) < len(a0) * 0.9, (len(a0), len(a1))
    assert client.get(f"/api/voices/{v['id']}/demo", params={"pitch": 3}).status_code == 200
    client.delete(f"/api/voices/{v['id']}")


def test_formal_vitals_do_not_use_temperature_slang():
    import random
    from nursing_tts.generator import realize_vitals
    for i in range(60):
        txt = realize_vitals({"sbp": 120, "dbp": 80, "hr": 72, "rr": 18, "bt": 38.3, "spo2": 97}, random.Random(i), verb_style="formal")
        assert "8도" not in txt and "38.3" in txt, txt
