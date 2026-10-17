"""대화형 간호정보조사 (2026-10-17): nurse asks, patient answers; 반말 from 80; two voices in the recording."""
import random
import re

from nursing_tts.dialogue import strip_prefix, to_banmal
from nursing_tts.fake import random_datetime, random_form, random_patient
from nursing_tts.generator import build_script


def test_dialogue_turns_follow_the_form_and_the_patients_age():
    rng = random.Random(5)
    young = old = 0
    for i in range(120):
        p = random_patient(rng, "s1")
        f = random_form("s1", rng, p)
        s = build_script("s1", f, p, random_datetime(rng), style="formal", seed=i, dialogue=True)
        lines = s.spoken_text.splitlines()
        assert len(s.turns) == len(lines) and [t["text"] for t in s.turns] == lines
        assert s.turns[0]["speaker"] == "nurse" and s.turns[-1]["speaker"] == "nurse"
        patient_lines = [t["text"] for t in s.turns if t["speaker"] == "patient"]
        nurse_q = [t["text"] for t in s.turns if t["speaker"] == "nurse" and t["text"].rstrip().endswith("?")]
        assert len(patient_lines) >= 8 and len(nurse_q) >= 8, (len(patient_lines), len(nurse_q))
        assert all("?" not in t for t in patient_lines)
        for k, t in enumerate(s.turns[:-1]):
            if t["speaker"] == "nurse" and t["text"].rstrip().endswith("?"):
                assert s.turns[k + 1]["speaker"] == "patient", t
        if (p.age or 0) >= 80:
            old += 1
            assert not any(re.search(r"(요|니다)[.!?]$", t) for t in patient_lines), patient_lines
            assert not any(t.startswith("네") or t.startswith("아니오") for t in patient_lines), patient_lines
        else:
            young += 1
            assert all(re.search(r"(요|니다|네|예)[.!]$", t) for t in patient_lines), patient_lines
        # the answers follow the chart: fall history, history, pain
        joined = " ".join(patient_lines)
        if f.get("fall_history") == "yes":
            assert "넘어" in joined
        if int(f.get("nrs") or 0) == 0:
            assert "점 정도" not in joined
        else:
            assert f"{f['nrs']}점" in joined
        if "htn" in (f.get("history") or []):
            assert "고혈압" in joined
        assert "(이)랑" not in joined and "{" not in s.spoken_text
        assert "?" not in s.tts_text.splitlines()[0]
    assert young >= 60 and old >= 5


def test_banmal_and_prefix_helpers():
    assert to_banmal("네, 당뇨랑 고혈압 있어요. 천주교예요. 수술은 처음이에요.") == "응, 당뇨랑 고혈압 있어. 천주교야. 수술은 처음이야."
    assert to_banmal("아니오, 없어요.") == "아니, 없어."
    assert strip_prefix("환자: 네, 잘 먹어요.") == ("patient", "네, 잘 먹어요.")
    assert strip_prefix("간호사: 잠은 잘 주무세요?") == ("nurse", "잠은 잘 주무세요?")
    assert strip_prefix("그냥 문장.") == ("nurse", "그냥 문장.")


def test_dialogue_recording_has_two_speakers(tmp_path, monkeypatch):
    from nursing_tts import jobs
    from nursing_tts.config import save_settings
    monkeypatch.setenv("NURSING_TTS_DATA", str(tmp_path))
    save_settings({"tts_engine": "silent", "asr_verify": False})
    rng = random.Random(9)
    p = random_patient(rng, "s1")
    f = random_form("s1", rng, p)
    spec = {"template": "s1", "form": f, "patient": p.__dict__, "datetime": "2026-10-17T09:00", "style": "formal", "seed": 4,
            "dialogue": True, "patient_voice_id": "same", "noise": {"enabled": False}}
    meta = jobs.generate_one(spec, {"tts_engine": "silent", "sample_rate": 24000, "loudness_dbfs": -20.0}, [])
    assert meta["dialogue"] and {t["speaker"] for t in meta["turns"]} == {"nurse", "patient"}
    assert {sg["speaker"] for sg in meta["segments"]} == {"nurse", "patient"}
    assert meta["duration_sec"] > 1 and meta["patient_shift"]["pitch"] != 0
    assert (tmp_path / "output").exists() or meta["file"]
    # hand-edited text keeps the speakers through the "환자:" prefix
    spec2 = {**spec, "text_override": "2026년 10월 17일 오전 9시 " + p.name + " 님 간호정보조사 기록입니다.\n간호사: 잠은 잘 주무세요?\n환자: 네, 잘 자요.\n이상 간호정보조사 마치겠습니다."}
    meta2 = jobs.generate_one(spec2, {"tts_engine": "silent", "sample_rate": 24000, "loudness_dbfs": -20.0}, [])
    assert [t["speaker"] for t in meta2["turns"]] == ["nurse", "nurse", "patient", "nurse"]
    assert "환자:" not in meta2["spoken_text"] and "네, 잘 자요." in meta2["spoken_text"]


def test_dialogue_opens_with_how_did_you_come_in_and_extracts_the_chart(monkeypatch):
    """user 2026-10-17: the interview starts with "어떻게 오셨어요?", the patient tells the story in lay words (sometimes
    rambling or unsure), and the nurse pins the chart facts (주호소·발생 시기·경로·목적) in one confirmation line."""
    from nursing_tts import dialogue as d
    rng = random.Random(21)
    vague = chemo = 0
    for i in range(150):
        p = random_patient(rng, "s1")
        f = random_form("s1", rng, p)
        s = build_script("s1", f, p, random_datetime(rng), style="formal", seed=3000 + i, dialogue=True)
        qs = [k for k, t in enumerate(s.turns) if t["speaker"] == "nurse" and t["text"].rstrip().endswith("?")]
        first_q = qs[0]
        assert s.turns[first_q]["text"] in d.OPENERS, s.turns[first_q]["text"]
        assert all(t["speaker"] == "nurse" and not t["text"].endswith("?") for t in s.turns[:first_q])   # signal/intro only before it
        story = s.turns[first_q + 1]
        assert story["speaker"] == "patient" and "?" not in story["text"]
        assert len(re.findall(r"[.!]", story["text"])) >= 2, story["text"]                                 # a story, not one word
        confirm = s.turns[first_q + 2]
        assert confirm["speaker"] == "nurse" and not confirm["text"].endswith("?")
        cc = str(f.get("chief_complaint") or "")
        assert cc in confirm["text"], (cc, confirm["text"])                                              # exact chart wording survives
        assert "(이)" not in confirm["text"] and "(으)" not in confirm["text"] and "{" not in s.spoken_text
        nurse_lines = [t["text"] for t in s.turns if t["speaker"] == "nurse"]
        assert sum(cc in l for l in nurse_lines) == 1, cc                                                 # not narrated a second time
        patient_lines = [t["text"] for t in s.turns if t["speaker"] == "patient"]
        for w in ("소견", "촉지", "예정", "경유", "주호소", "CT", "MRI"):                                  # chart jargon stays with the nurse
            assert not any(w in t for t in patient_lines), (w, patient_lines)
        joined = " ".join(patient_lines)
        if "기억이 안 나" in joined or "모르겠" in joined:
            vague += 1
        if p.kind == "chemo":
            chemo += 1
            assert "항암" in story["text"]
        if f.get("route") == "er":
            assert "응급실" in story["text"] or p.kind == "chemo"
        for k, t in enumerate(s.turns[1:-1], 1):                                                         # a follow-up after a vague surgery answer
            prev = s.turns[k - 1]["text"]
            if t["speaker"] == "patient" and ("기억이 안 나" in t["text"] or "모르겠" in t["text"]) and prev.endswith("?") and "수술" in prev:
                nxt = s.turns[k + 1]
                assert nxt["speaker"] == "nurse" and ("하셨고요" in nxt["text"] or "맹장 수술" in nxt["text"]), (t["text"], nxt["text"])
    assert vague >= 15 and chemo >= 3, (vague, chemo)
    # a known complaint has lay wording with the trauma cause in front
    assert d.lay_complaint("낙상 후 어깨 통증과 변형", random.Random(1))[0].startswith("넘어져서 어깨")
    assert d.lay_complaint("배변 후 항문에서 선홍색 출혈", random.Random(1)) == ["변 볼 때 피가 났어요."]
