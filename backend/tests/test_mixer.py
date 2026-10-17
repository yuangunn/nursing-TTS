

def test_event_clips_play_as_spaced_episodes(tmp_path):
    """user 2026-10-17 ("소리가 들쭉날쭉"): a 40 s alarm recording is not stacked on itself — episodes of 8–20 s, never
    overlapping the same clip, covering at most about a third of the recording, and the json says when each one plays."""
    import numpy as np, soundfile as sf
    from nursing_tts.audio.mixer import NoiseClip, NoiseConfig, mix
    sr = 24000
    alarm = (0.5 * np.sin(2 * np.pi * 1300 * np.arange(40 * sr) / sr)).astype(np.float32)
    sf.write(tmp_path / "alarm.wav", alarm, sr)
    bed = (0.05 * np.random.default_rng(0).standard_normal(30 * sr)).astype(np.float32)
    sf.write(tmp_path / "bed.wav", bed, sr)
    clips = [NoiseClip(id="alarm", label="환자 모니터 알람", path=tmp_path / "alarm.wav", continuous=False, gain=0.6),
             NoiseClip(id="bed", label="병실 배경음", path=tmp_path / "bed.wav", continuous=True, gain=0.5)]
    speech = (0.1 * np.random.default_rng(1).standard_normal(120 * sr)).astype(np.float32)
    for seed in range(6):
        _, events = mix(speech, sr, NoiseConfig(enabled=True, level=30, types=["alarm", "bed"], each_prob=1.0, density=4, seed=seed, head_pad=0, tail_pad=0), clips)
        eps = sorted((e["start"], e["duration"]) for e in events if e["type"] == "alarm")
        assert 1 <= len(eps) <= 4, eps
        assert all(8 <= d <= 20.5 for _, d in eps), eps
        assert all(a[0] + a[1] <= b[0] + 0.01 for a, b in zip(eps, eps[1:])), eps            # never on top of itself
        assert sum(d for _, d in eps) <= 0.4 * 120, eps
        assert [e for e in events if e["type"] == "bed"][0]["start"] == 0.0
