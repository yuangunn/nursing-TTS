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


def test_sentence_chunks_and_real_pause_distribution():
    import random
    from nursing_tts.tts.base import chunk_sentences, natural_pause, synthesize_paragraphs

    # short sentences ride along with a neighbour (leading ones forward, a trailing one backward)
    assert chunk_sentences("격리 아닙니다. 풀 코드입니다. 보호자는 배우자이고 연락처 확인했습니다. 끝.") == \
        ["격리 아닙니다. 풀 코드입니다. 보호자는 배우자이고 연락처 확인했습니다. 끝."]
    chunks = chunk_sentences("의식 명료하고 열 삼십칠 점 사까지 올라서 해열제 들어갔습니다. 통증 엔알에스 삼 점이에요. 피씨에이 유지 중이고 데이 때 트라마돌 한 번 들어갔습니다.")
    assert chunks == ["의식 명료하고 열 삼십칠 점 사까지 올라서 해열제 들어갔습니다.",
                      "통증 엔알에스 삼 점이에요. 피씨에이 유지 중이고 데이 때 트라마돌 한 번 들어갔습니다."]

    class Tone:
        key, label, clones_voice = "tone", "tone", False
        calls = 0

        def synthesize(self, text, ref, seed=None):
            self.calls += 1
            return np.ones(24000, dtype=np.float32) * 0.1, 24000

    eng = Tone()
    audio, sr = synthesize_paragraphs(eng, ["첫 문단의 첫 번째 문장이고 스무 글자를 넘기려고 길게 씁니다. 첫 문단의 두 번째 문장도 스무 글자를 넘기려고 길게 씁니다.",
                                            "둘째 문단은 한 문장뿐이지만 역시 스무 글자를 넘기려고 길게 씁니다."], None, seed=1)
    assert eng.calls == 3
    pause_total = len(audio) / sr - 3.0
    assert 2 * 0.25 <= pause_total <= 2 * 3.5
    rng = random.Random(0)
    p = sorted(natural_pause(rng) for _ in range(2000))
    assert 0.45 < p[1000] < 0.8 and 1.2 < p[1800] < 2.2 and p[-1] <= 3.5 and p[0] >= 0.25


def test_rounds_dialogue_renders_far_away():
    import random
    from nursing_tts import rounds

    rng = random.Random(3)
    d = rounds.make_dialogue(rng, turns=6)
    assert len(d) == 6 and d[0][0] == "doctor" and d[1][0] == "patient"

    class Tone:
        key, label, clones_voice = "tone", "tone", False

        def synthesize(self, text, ref, seed=None):
            t = np.arange(int(1.5 * 24000)) / 24000
            return (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32), 24000

    audio, dialogue = rounds.render(Tone(), random.Random(3), sr=24000, turns=4)
    assert len(dialogue) == 4
    assert 4 * 1.5 <= len(audio) / 24000 <= 4 * 1.5 / 0.9 + 3 * 3.5 + 1
    assert np.isfinite(audio).all() and 0 < np.max(np.abs(audio)) <= 1.0


def test_trim_silence_cuts_model_tail():
    from nursing_tts.tts.base import trim_silence

    sr = 24000
    speech = np.concatenate([np.zeros(sr), np.ones(sr) * 0.2, np.zeros(3 * sr)]).astype(np.float32)
    out = trim_silence(speech, sr)
    assert 1.0 <= len(out) / sr <= 1.15
    assert len(trim_silence(np.zeros(sr, dtype=np.float32), sr)) == sr  # all-silent input untouched


def test_rounds_pitch_shift_moves_fundamental():
    from nursing_tts.rounds import pitch_shift

    sr = 24000
    t = np.arange(2 * sr) / sr
    tone = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    low = pitch_shift(tone, sr, -12)
    spec = np.abs(np.fft.rfft(low[: sr]))
    peak_hz = np.fft.rfftfreq(sr, 1 / sr)[np.argmax(spec)]
    assert 200 <= peak_hz <= 240, peak_hz
    assert pitch_shift(tone, sr, 0) is tone
