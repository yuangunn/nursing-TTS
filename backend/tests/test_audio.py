import numpy as np

from nursing_tts.audio import noise
from nursing_tts.audio.mixer import NoiseConfig, level_to_snr_db, mix
from nursing_tts.audio.io import rms


def test_all_builtin_noises_render():
    rng = np.random.default_rng(0)
    for key, nt in noise.BUILTIN.items():
        dur = 3.0 if nt.continuous else max(nt.min_dur, 1.0)
        a = noise.render(key, dur, 24000, rng)
        assert a.dtype == np.float32 and len(a) > 0
        assert np.isfinite(a).all()
        assert np.max(np.abs(a)) <= 1.01


def test_mix_snr():
    sr = 24000
    t = np.arange(int(6 * sr)) / sr
    speech = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    cfg = NoiseConfig(enabled=True, level=50, types=["room_tone", "monitor_pulse", "crowd_babble"], seed=1, head_pad=0, tail_pad=0)
    mixed, events = mix(speech, sr, cfg)
    assert len(mixed) == len(speech)
    assert events
    ambience = mixed - speech
    snr = 20 * np.log10(rms(speech) / rms(ambience))
    assert abs(snr - level_to_snr_db(50)) < 1.5


def test_mix_disabled_only_pads():
    sr = 24000
    speech = np.ones(sr, dtype=np.float32) * 0.1
    cfg = NoiseConfig(enabled=False, head_pad=0.5, tail_pad=0.5)
    mixed, events = mix(speech, sr, cfg)
    assert len(mixed) == 2 * sr and not events
