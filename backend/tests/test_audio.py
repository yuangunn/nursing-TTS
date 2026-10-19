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
    # the SNR mapping is measured on the ambience alone (the always-on room reverb of the speech and the room-tone floor
    # would otherwise count as "noise" in mixed - speech)
    cfg = NoiseConfig(enabled=True, level=50, types=["room_tone", "monitor_pulse", "crowd_babble"], each_prob=1.0, seed=1, head_pad=0, tail_pad=0, room_wet=0.0, floor_dbfs=0)
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
    assert 1.0 <= len(out) / sr <= 1.4  # 3 s model tail gone, 0.18 s natural decay kept
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


def test_rounds_tempo_per_role_and_settings_override():
    import random
    from nursing_tts.rounds import render, time_stretch

    sr = 24000
    t = np.arange(2 * sr) / sr
    tone = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    fast = time_stretch(tone, 1.25)
    assert abs(len(fast) / sr - 1.6) < 0.1
    assert time_stretch(tone, 1.0) is tone

    class Tone:
        key, label, clones_voice = "tone", "tone", True

        def synthesize(self, text, ref, seed=None):
            return tone.copy(), sr

    rng = random.Random(5)
    slow, d = render(Tone(), rng, sr=sr, turns=3, ref=(__import__("pathlib").Path("x.wav"), ""),
                     shift={"doctor": 0, "patient": 0, "nurse": 0}, tempo={"doctor": 0.7, "patient": 0.7, "nurse": 0.7}, jitter=0)
    fast, _ = render(Tone(), random.Random(5), sr=sr, turns=3, ref=(__import__("pathlib").Path("x.wav"), ""),
                     shift={"doctor": 0, "patient": 0, "nurse": 0}, tempo={"doctor": 1.4, "patient": 1.4, "nurse": 1.4}, jitter=0)
    assert len(slow) > len(fast) * 1.3


def test_synthesize_paragraphs_uses_batched_engine():
    from nursing_tts.tts.base import synthesize_paragraphs

    class Batched:
        key, label, clones_voice = "b", "b", True
        calls: list[list[str]] = []

        def synthesize(self, text, ref, seed=None):
            raise AssertionError("batched engines must not be called one by one")

        def synthesize_many(self, texts, ref, seed=None):
            self.calls.append(list(texts))
            return [np.ones(24000, dtype=np.float32) * 0.1 for _ in texts], 24000

    eng = Batched()
    audio, sr = synthesize_paragraphs(eng, ["첫 문단의 첫 번째 문장이고 스무 글자를 넘기려고 길게 씁니다. 첫 문단의 두 번째 문장도 스무 글자를 넘기려고 길게 씁니다.",
                                            "둘째 문단은 한 문장뿐이지만 역시 스무 글자를 넘기려고 길게 씁니다."], None, seed=1)
    assert len(eng.calls) == 1 and len(eng.calls[0]) == 3
    assert 3.0 + 2 * 0.25 <= len(audio) / sr <= 3.0 + 2 * 3.5


def test_synthesize_script_segments_have_exact_times_and_ground_truth():
    from nursing_tts.tts.base import plan_chunks, synthesize_script

    spoken = ["혈압 135/80, 맥박 88입니다. 체온 37.2도입니다. 통증은 NRS 3점으로 조절되고 있습니다.", "끝."]
    tts = ["혈압 백삼십오 에 팔십, 맥박 팔십팔입니다. 체온 삼십칠 점 이 도입니다. 통증은 엔알에스 삼 점으로 조절되고 있습니다.", "끝."]
    plan = plan_chunks(spoken, tts)
    assert [p[1] for p in plan] == ["혈압 135/80, 맥박 88입니다. 체온 37.2도입니다.", "통증은 NRS 3점으로 조절되고 있습니다.", "끝."]
    assert all("점" not in p[1] or "NRS" in p[1] or "점" in p[1] for p in plan)  # spoken keeps digits
    # mismatched sentence counts fall back to one chunk per paragraph
    assert plan_chunks(["하나. 둘."], ["하나 둘."]) == [(0, "하나. 둘.", "하나 둘.", True)]

    class Tone:
        key, label, clones_voice = "tone", "tone", False

        def synthesize(self, text, ref, seed=None):
            return np.ones(int(0.5 * 24000), dtype=np.float32) * 0.1, 24000

    audio, sr, segs = synthesize_script(Tone(), spoken, tts, None, seed=1)
    assert len(segs) == 3 and segs[0]["start"] == 0 and segs[0]["text"].startswith("혈압 135/80")
    assert all(abs((s["end"] - s["start"]) - 0.5) < 0.02 for s in segs)
    assert all(segs[i]["end"] <= segs[i + 1]["start"] for i in range(2))
    assert abs(segs[-1]["end"] - len(audio) / sr) < 0.01


def test_pauses_get_a_room_tone_floor_and_light_room_even_with_noise_off():
    from nursing_tts.audio.mixer import NoiseConfig, mix
    from nursing_tts.audio.io import rms

    sr = 24000
    speech = np.concatenate([np.ones(sr) * 0.2, np.zeros(sr), np.ones(sr) * 0.2]).astype(np.float32)
    out, events = mix(speech, sr, NoiseConfig(enabled=False, head_pad=0, tail_pad=0, seed=1))
    gap = out[int(1.3 * sr):int(1.7 * sr)]
    assert not events and len(out) == len(speech)
    assert -62 < 20 * np.log10(rms(gap) + 1e-9) < -50          # ≈ -56 dBFS bed, not digital silence
    silent, _ = mix(speech, sr, NoiseConfig(enabled=False, head_pad=0, tail_pad=0, floor_dbfs=0, room_wet=0))
    assert rms(silent[int(1.3 * sr):int(1.7 * sr)]) < 1e-6      # knobs at 0 restore the old behaviour


def test_trim_silence_keeps_tail_and_fades_edges():
    from nursing_tts.tts.base import trim_silence

    sr = 24000
    speech = np.concatenate([np.zeros(sr), np.ones(sr) * 0.2, np.zeros(3 * sr)]).astype(np.float32)
    out = trim_silence(speech, sr)
    assert 1.3 <= len(out) / sr <= 1.4          # 0.18 s kept on each side
    assert out[0] == 0 and out[-1] == 0 and 0 < out[int(0.19 * sr)] <= 0.2  # faded edges, body intact


def test_bad_sentences_are_resynthesized_until_readback_passes():
    from nursing_tts.tts.base import synthesize_script

    class Engine:
        key, label, clones_voice = "e", "e", True
        calls: list[list[str]] = []

        def synthesize_many(self, texts, ref, seed=None):
            self.calls.append(list(texts))
            # take number is encoded in the amplitude so the fake verifier can tell takes apart, and in the length
            # because the joined audio is leveled per sentence
            amp = 0.1 * (len(self.calls))
            return [np.ones(24000 + 2400 * len(self.calls), dtype=np.float32) * amp for _ in texts], 24000

    def verify(spoken, tts, audio, sr):
        take = round(float(audio.max()) / 0.1)
        if "둘째" in spoken:
            return 0.9 if take < 3 else 0.05   # bad on take 1 and 2, good on take 3
        return 0.02

    eng = Engine()
    lines = ["첫째 문장은 처음부터 잘 읽혀서 다시 만들 필요가 없습니다.", "둘째 문장은 두 번 다시 만들어야 통과하는 문장입니다.",
             "셋째 문장도 처음부터 잘 읽혀서 그대로 둡니다."]
    audio, sr, segs = synthesize_script(eng, lines, lines, None, seed=1, verify=verify, cer_threshold=0.3, retries=2)
    assert [len(c) for c in eng.calls] == [3, 1, 1]          # all chunks, then only the bad one twice
    assert [s["retries"] for s in segs] == [0, 2, 0]
    assert segs[1]["cer"] == 0.05 and segs[0]["cer"] == 0.02
    assert abs(segs[1]["end"] - segs[1]["start"] - 1.3) < 1e-3   # the third take of the bad chunk is what got kept


def test_only_real_clips_are_offered_and_each_is_mixed_probabilistically(tmp_path):
    import numpy as np
    import soundfile as sf
    from nursing_tts.audio.mixer import NoiseClip, NoiseConfig, mix
    from nursing_tts import noise_library
    assert all(not it["builtin"] for it in noise_library.catalogue())   # no synthetic noises in the catalogue
    sr = 24000
    rng = np.random.default_rng(1)
    clips = []
    for i, cont in enumerate((True, False, False)):
        p = tmp_path / f"clip{i}.wav"
        sf.write(p, (0.2 * rng.standard_normal(sr * 3)).astype("float32"), sr)
        clips.append(NoiseClip(id=f"c{i}", label=f"실제 소음 {i}" if i else "병실 룸톤", path=p, category="custom", continuous=cont, gain=0.5))
    speech = np.zeros(sr * 6, dtype="float32")
    seen = set()
    for seed in range(12):   # types empty -> all real clips, each with each_prob; never an empty pick
        _, events = mix(speech, sr, NoiseConfig(enabled=True, level=40, types=[], each_prob=0.5, seed=seed, head_pad=0, tail_pad=0), custom=clips)
        types = {e["type"] for e in events}
        assert types and types <= {"c1", "c2"}, types   # c0 is the room tone: floor only, never a picked noise
        seen |= types
    assert seen == {"c1", "c2"}


def test_qwen_generation_has_a_length_ceiling():
    """2026-10-18: without max_new_tokens one runaway sentence ran a batch to the 8192-token default (23 GB, hours)."""
    from nursing_tts.tts.qwen import _token_cap
    assert _token_cap(["환자분 통증 없다고 하십니다."]) < 400          # a short sentence cannot run for minutes
    assert _token_cap(["가" * 150]) >= 150 / 2 * 12.5                   # 150 syllables at 2 per second still fit
    assert _token_cap(["가" * 5000]) == 8192


def test_qwen_decodes_a_batch_one_sentence_at_a_time():
    """2026-10-18: the library padded a batch to its longest sentence and decoded it at once (+8 GB on MPS)."""
    from nursing_tts.tts.qwen import _decode_one_by_one

    class Tok:
        calls = []

        def decode(self, encoded):
            self.calls.append(len(encoded))
            return [f"wav{len(self.calls)}"] * len(encoded), 24000
    tok = Tok()
    _decode_one_by_one(tok)
    assert tok.decode([{"audio_codes": 1}, {"audio_codes": 2}, {"audio_codes": 3}]) == (["wav1", "wav2", "wav3"], 24000)
    assert Tok.calls == [1, 1, 1]


def test_chunk_retry_uses_another_reference_clip():
    """2026-10-18: one sentence stuttered for 42 s in all three takes with the same prompt clip; retries switch clips."""
    import numpy as np
    from nursing_tts.tts.base import synthesize_script
    used = []

    class Eng:
        def synthesize_many(self, texts, ref, seed=None):
            used.append(ref[1])
            return [np.full(4800, 0.1 if ref[1] == "A" else 0.2, dtype=np.float32) for _ in texts], 24000
    verify = lambda sp, tt, a, sr: 0.9 if float(np.abs(a).max()) < 0.15 else 0.0   # every take with clip A is unreadable
    line = "금일 오후 퇴원 예정이며 퇴원약에 대해 교육하였습니다."
    _, _, segs = synthesize_script(Eng(), [line], [line], ("a.wav", "A"), 1, verify=verify, retries=2, retry_refs=[("b.wav", "B")])
    assert used == ["A", "B"] and segs[0]["cer"] == 0.0


def test_sentences_are_leveled_to_one_speech_level():
    """2026-10-19 user: "마스터링이 잘 안되어있어" — one voice's prompt clips differ by 16 dB and the clone copies the level."""
    from nursing_tts.tts.base import synthesize_script

    class Eng:
        def synthesize_many(self, texts, ref, seed=None):
            return [np.full(24000, a, dtype=np.float32) for a, _ in zip([0.02, 0.3, 0.1], texts)], 24000
    lines = ["첫 번째 문장은 스무 글자를 넘기려고 길게 씁니다. 두 번째 문장도 스무 글자를 넘기려고 길게 씁니다. 세 번째 문장도 스무 글자를 넘기려고 길게 씁니다."]
    audio, sr, segs = synthesize_script(Eng(), lines, lines, ("a.wav", "A"), 1)
    levels = [20 * np.log10(np.sqrt(np.mean(audio[int(s["start"] * sr) + 2000: int(s["end"] * sr) - 2000] ** 2))) for s in segs]
    assert len(levels) == 3 and max(levels) - min(levels) < 0.5 and abs(levels[0] + 20) < 0.5


def test_qwen_reference_ends_in_silence_and_a_closed_sentence():
    """2026-10-19: tight clips + transcripts without a period made the clone swallow "양치," / "환자," and clip "…십니다"."""
    from nursing_tts.tts.qwen import _prepare_reference
    audio, text = _prepare_reference(np.full(24000, 0.03, dtype=np.float32), 24000, "약이나 식품에 알러지 없으십니다 ")
    assert text == "약이나 식품에 알러지 없으십니다."
    assert len(audio) == 36000 and not audio[24000:].any()
    assert abs(20 * np.log10(np.sqrt(np.mean(audio[:24000] ** 2))) + 20) < 0.5
    assert _prepare_reference(np.full(2400, 0.1, dtype=np.float32), 24000, "있으세요?")[1] == "있으세요?"


def test_qwen_sentences_end_with_a_pause_mark():
    """2026-10-19 user: "~십니다." came out as "~십니ㄷ" — the model input ends in "..." so the last syllable is finished."""
    from nursing_tts.tts.qwen import _end_with_pause
    assert _end_with_pause("집에서 드시던 약은 없다고 하십니다.") == "집에서 드시던 약은 없다고 하십니다..."
    assert _end_with_pause("드시는 약 있으세요?") == "드시는 약 있으세요?"
    assert _end_with_pause("기다려 주세요...") == "기다려 주세요..."
