import random

from nursing_tts import voices


def test_reference_follows_record_style(tmp_path, monkeypatch):
    monkeypatch.setenv("NURSING_TTS_DATA", str(tmp_path))
    v = voices.create_voice("문진 간호사", "", "여")
    import numpy as np
    from nursing_tts.audio.io import write_wav
    q = tmp_path / "q.wav"; d = tmp_path / "d.wav"
    write_wav(q, np.zeros(24000 * 9, dtype=np.float32), 24000)
    write_wav(d, np.zeros(24000 * 9, dtype=np.float32), 24000)
    voices.add_sample(v.id, q, "혹시 과거에 앓으셨던 질환 있으실까요? 없으시고요", "auto")
    voices.add_sample(v.id, d, "과거력은 고혈압 10년으로 약 복용 중입니다.", "auto")
    rng = random.Random(0)
    for _ in range(10):
        assert "까요" in voices.pick_reference(v.id, rng=rng, style="interview")[1]
        assert "까요" not in voices.pick_reference(v.id, rng=rng, style="dictation")[1]
    assert voices.sample_style("체온 37도 측정됨") == "dictation"
