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
    assert {t["key"] for t in ts} == {"s1", "s2", "s3_1", "s3_2", "s4", "s5"}
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
