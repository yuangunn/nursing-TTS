"""목소리 학습 (2026-10-19 user: "앱에 학습기능 추가해줘. 미세조정하자"): datasets, the trainer process, trained voices."""
import io
import subprocess
import sys

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from nursing_tts import finetune, voices
from nursing_tts.config import save_settings
from nursing_tts.server import app

client = TestClient(app)


def _tone(seconds, sr=24000):
    t = np.arange(int(seconds * sr)) / sr
    return (0.2 * np.sin(2 * np.pi * 180 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t))).astype(np.float32)


def _wav(audio, sr=24000):
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")
    return buf.getvalue()


def _voice_with_clips(n=6):
    v = client.post("/api/voices", json={"name": "학습용 간호사", "sex": "여"}).json()
    for k in range(n):
        r = client.post(f"/api/voices/{v['id']}/samples", files={"file": ("c.wav", _wav(_tone(3.0)), "audio/wav")},
                        data={"transcript": f"{k}번째 문장입니다"})
        assert r.status_code == 200, r.text
    return v


def test_dataset_from_a_voice_pads_clips_and_takes_edits():
    save_settings({"tts_engine": "silent"})
    v = _voice_with_clips()
    s = client.post("/api/finetune/datasets/from-voice", json={"voice_id": v["id"]}).json()
    assert s["items"] == 6 and s["included"] == 6 and s["confirmed"] == 0 and s["minutes"] > 0
    ds = client.get(f"/api/finetune/datasets/{s['id']}").json()
    sample = voices.get_voice(v["id"]).samples[0]
    assert abs(ds["clips"][0]["duration"] - (sample.duration + 2 * finetune.PAD_S)) < 0.02   # silence around tight clips
    c = ds["clips"][0]
    r = client.patch(f"/api/finetune/datasets/{s['id']}/clips/{c['id']}", json={"text": " 어, 영번째 문장입니다 ", "confirmed": True})
    assert r.json()["text"] == "어, 영번째 문장입니다" and r.json()["confirmed"] is True
    client.patch(f"/api/finetune/datasets/{s['id']}/clips/{ds['clips'][1]['id']}", json={"include": False})
    after = client.get(f"/api/finetune/datasets/{s['id']}").json()
    assert after["included"] == 5 and after["confirmed"] == 1
    assert client.get(f"/api/finetune/datasets/{s['id']}/clips/{c['id']}/audio").status_code == 200
    assert any(d["id"] == s["id"] for d in client.get("/api/finetune/datasets").json())
    assert client.post("/api/finetune/datasets/from-voice", json={"voice_id": "nope"}).status_code == 404


def test_dataset_from_a_long_recording_cuts_at_pauses_with_real_surroundings():
    sr = 24000
    gap = np.zeros(int(0.8 * sr), dtype=np.float32)
    long = np.concatenate([np.concatenate([_tone(4.0), gap]) for _ in range(5)])
    r = client.post("/api/finetune/datasets/from-recordings", files=[("files", ("long.wav", _wav(long), "audio/wav"))],
                    data={"name": "인계 녹음", "transcribe": "false"})
    assert r.status_code == 200, r.text
    ds = client.get(f"/api/finetune/datasets/{r.json()['id']}").json()
    assert len(ds["clips"]) >= 2 and all(3.0 <= c["duration"] <= 15.0 for c in ds["clips"])
    assert all(not c["include"] for c in ds["clips"])     # no transcript yet -> left out until someone writes one
    silent = client.post("/api/finetune/datasets/from-recordings", files=[("files", ("s.wav", _wav(np.zeros(sr * 2, np.float32)), "audio/wav"))],
                         data={"transcribe": "false"})
    assert silent.status_code == 400


def test_training_process_lifecycle(monkeypatch):
    """Real child process (a sleeper stands in for the trainer): start -> active, synthesis refused, cancel; then a
    finished adapter becomes a voice that hands the engine its folder."""
    v = _voice_with_clips()
    ds = client.post("/api/finetune/datasets/from-voice", json={"voice_id": v["id"]}).json()

    def fake_spawn(d):
        with finetune._LOCK:
            finetune._PROC[d.name] = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    monkeypatch.setattr(finetune, "_spawn", fake_spawn)
    monkeypatch.setattr(finetune, "available", lambda: (True, "test"))
    few = client.post("/api/finetune/datasets/from-voice", json={"voice_id": _voice_with_clips(2)["id"]}).json()
    assert client.post("/api/finetune/train", json={"dataset_id": few["id"]}).status_code == 400   # fewer than MIN_ITEMS

    st = client.post("/api/finetune/train", json={"dataset_id": ds["id"], "name": "간호사 학습", "epochs": 3}).json()
    assert st["running"] and st["epochs"] == 3 and finetune.active() == st["id"]
    assert client.post("/api/finetune/train", json={"dataset_id": ds["id"]}).status_code == 400    # one at a time
    from nursing_tts.tts.qwen import QwenEngine
    try:
        QwenEngine().synthesize_many(["문장입니다."], ("a.wav", "전사"))
        raise AssertionError("synthesis must be refused while training")
    except RuntimeError as e:
        assert "학습 중" in str(e)
    c = client.post(f"/api/finetune/models/{st['id']}/cancel").json()
    assert c["stage"] == "cancelled" and not c["running"] and finetune.active() is None

    # what the trainer does at the end: adapter on disk -> a voice that speaks through it
    st2 = client.post("/api/finetune/train", json={"dataset_id": ds["id"], "name": "간호사 학습"}).json()
    finetune.cancel(st2["id"])
    d = finetune.model_dir(st2["id"])
    (d / "adapter.pt").write_bytes(b"x")
    vid = finetune._register_voice(d, finetune.status(st2["id"]), "test")
    tv = voices.get_voice(vid)
    assert tv.model == st2["id"] and tv.sex == "여" and not tv.samples
    assert voices.pick_reference(vid) == (d, "")
    assert finetune.status(st2["id"])["ready"]
    assert any(m["id"] == st2["id"] for m in client.get("/api/finetune/models").json())
    client.delete(f"/api/finetune/models/{st2['id']}")
    assert voices.get_voice(vid) is None and not d.exists()


def test_training_waits_for_running_recordings(monkeypatch):
    from nursing_tts import jobs
    v = _voice_with_clips()
    ds = client.post("/api/finetune/datasets/from-voice", json={"voice_id": v["id"]}).json()
    monkeypatch.setattr(finetune, "available", lambda: (True, "test"))
    monkeypatch.setattr(jobs, "list_jobs", lambda: [{"status": "running"}])
    assert client.post("/api/finetune/train", json={"dataset_id": ds["id"]}).status_code == 409


def test_engine_speaks_a_trained_voice_through_custom_voice(monkeypatch, tmp_path):
    import contextlib
    from nursing_tts.tts import qwen
    calls = []

    class FakeModel:
        def generate_custom_voice(self, text, speaker, language, max_new_tokens):
            calls.append(("custom", text, speaker, language))
            return [np.full(2400, 0.1, dtype=np.float32) for _ in text], 24000

        def generate_voice_clone(self, **kw):
            calls.append(("clone",))
            return [np.zeros(2400, dtype=np.float32) for _ in kw["text"]], 24000
    used = []
    monkeypatch.setattr(finetune, "use", lambda m, d: (used.append(d), contextlib.nullcontext())[1])
    eng = qwen.QwenEngine(batch=4, idle_unload_min=0)
    monkeypatch.setattr(eng, "_load", lambda: FakeModel())
    (tmp_path / "adapter.pt").write_bytes(b"x")
    wavs, sr = eng.synthesize_many(["첫 문장입니다.", "두 번째 문장입니다."], (tmp_path, ""))
    assert used == [tmp_path] and len(wavs) == 2 and sr == eng.sr
    assert calls == [("custom", ["첫 문장입니다...", "두 번째 문장입니다..."], finetune.SPEAKER, "Auto")]


def test_room_tone_pads_with_the_clips_own_quiet_part():
    """Digital zeros around tight clips taught a silence the model never makes; it then waited ~2 s before stopping."""
    sr = 24000
    rng = np.random.default_rng(0)
    floor = (0.003 * rng.standard_normal(sr)).astype(np.float32)
    clip = np.concatenate([floor[: sr // 2], _tone(2.0), floor[sr // 2:]])
    pad = finetune.room_tone(clip, 0.25)
    assert len(pad) == int(0.25 * sr)
    rms = float(np.sqrt(np.mean(pad[500:-500] ** 2)))
    assert 0.002 < rms < 0.005                      # the clip's floor, not silence and not speech
    assert float(np.max(np.abs(np.diff(pad)))) < 0.03  # mirrored tiling: no clicks at the joins


def test_a_voice_saved_by_a_newer_version_still_loads():
    """v0.1.26 failed to list any voice once a trained voice (with ``model``) was on disk."""
    import json
    v = voices.create_voice("다음 버전 목소리")
    p = voices.voices_dir() / v.id / "voice.json"
    raw = json.loads(p.read_text(encoding="utf-8"))
    raw["future_field"] = 1
    raw["samples"] = [{"id": "s1", "file": "s1.wav", "transcript": "문장", "later": True}]
    p.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    assert any(x.id == v.id for x in voices.list_voices()) and voices.get_voice(v.id).samples[0].id == "s1"
