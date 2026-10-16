"""Scripts must not contain combinations a nurse would never chart (found by auditing 280 random scripts)."""
import random
import re
import zlib

from nursing_tts.fake import random_datetime, random_form, random_patient
from nursing_tts.generator import build_script

BAD = {
    "금연 금연": r"금연 금연", "숫자 뒤 이십니다": r"\d(?:\.\d)? ?이십니다", "측정한 측정한": r"(\S+) \1\b",
    "PCA 없이 PCA 교육": r"진통제 없이.*PCA 버튼", "의식 저하인데 대답": r"(stupor|confuse).*적절히 대답",
    "금식인데 식사": r"금식 유지.*(전량|절반) (섭취|드)", "소변줄 없는데 도뇨관 간호": r"소변줄 없이.*(도뇨관 (제거|고정|확인)|회음부)",
    "배액관 없는데 JP": r"배액관 없.*JP \d", "변화 없음 있": r"변화 없음 있", "풀코드": r"풀 ?코드|full code",
    "재사정이 더 아픔": r"통증 (\d+)점으로 (감소|호전)",
    "없음에 어미 붙음": r"없음(하여|으로|이고|이구요| 나왔)",
}


def _scripts(n_per_template=30):
    for t in ["s1", "s2", "s3_1", "s3_2", "s4", "s5", "s6"]:
        for i in range(n_per_template):
            rng = random.Random(7919 * i + zlib.crc32(t.encode()) % 997)
            p = random_patient(rng, t)
            s = build_script(t, random_form(t, rng, p), p, random_datetime(rng),
                             style=rng.choice(["mixed", "casual", "formal", "chart"]), seed=i, signal_format="random")
            yield t, p, s.spoken_text.replace("\n", " ")


def test_no_contradictory_or_awkward_sentences():
    hits = []
    for t, p, text in _scripts():
        for name, pat in BAD.items():
            m = re.search(pat, text)
            if not m:
                continue
            if name == "측정한 측정한" and m.group(1) in ("금연", "매우", "조금", "자주", "잘", "안"):  # legitimate repeats
                continue
            if name == "재사정이 더 아픔":
                before = re.search(r"(\d+)점(?:으로 사정함|\.)", text[: m.start()])
                if not before or int(m.group(1)) < int(before.group(1)):
                    continue
            hits.append((name, t, text[max(0, m.start() - 50): m.end() + 30]))
    assert not hits, "\n".join(f"{n} / {t}: …{s}…" for n, t, s in hits[:12])


def test_discharge_and_chemo_records_have_no_pca_or_catheter_items():
    for t, p, text in _scripts(20):
        if t == "s4":
            assert "PCA" not in text, text
        if p.kind == "chemo":
            assert "PCA" not in text and "도뇨관" not in text and "소변줄" not in text and "POD" not in text, text


def test_rare_states_are_rare():
    n = dnr = iso = 0
    for t, p, text in _scripts(40):
        if t != "s5":
            continue
        n += 1
        dnr += ("DNR" in text) or ("연명의료" in text)
        iso += ("격리 중" in text) or ("격리 적용" in text) or ("격리 환자" in text)
    assert dnr / n < 0.35 and iso / n < 0.35, (dnr, iso, n)


def test_young_non_ortho_patients_walk_independently():
    import random
    from nursing_tts.fake import random_form, random_patient
    rng = random.Random(9)
    n = dep = 0
    for _ in range(300):
        p = random_patient(rng, "s1")
        if p.department == "정형외과" or (p.age or 0) >= 70:
            continue
        f = random_form("s1", rng, p)
        n += 1
        dep += f.get("mobility") != "independent" or f.get("adl") != "independent"
    assert n > 50 and dep / n < 0.25, (dep, n)


def test_fall_and_pressure_scores_match_their_risk_bands():
    import random
    from nursing_tts.fake import braden_risk, fall_level, random_form, random_patient
    from nursing_tts.generator import build_script
    from nursing_tts.fake import random_datetime
    rng = random.Random(4)
    levels = set()
    for _ in range(200):
        p = random_patient(rng, "s1")
        f = random_form("s1", rng, p)
        assert f["fall"] == fall_level(f["jhfrat"]), (f["jhfrat"], f["fall"])
        levels.add(f["fall"])
        if f.get("skin") == "pressure":
            assert f["braden"] <= 14
        if "p_braden" in f:
            assert f["p_braden_risk"] == braden_risk(f["p_braden"])
        s = build_script("s1", f, p, random_datetime(rng), style="formal", seed=1)
        assert "Morse" not in s.spoken_text and "모스" not in s.spoken_text
        for w in ("Braden", "존스홉킨스", "JHFRAT", "브레이든"):
            assert w not in s.spoken_text, (w, s.spoken_text)          # ward talk: "낙상 n점으로 중위험군", never the tool name
        assert re.search(r"낙상 \d+점으로 .*위험", s.spoken_text) or "낙상 " in s.spoken_text, s.spoken_text
        assert f["pressure_risk"] == {"최고위험": "very_high", "고위험": "high", "중등도 위험": "moderate", "저위험": "low", "위험 없음": "none"}[braden_risk(f["braden"])]
        if f["fall"] != "high":
            assert not any(k.startswith("p_fall_") for k in f), [k for k in f if k.startswith("p_fall_")]
    assert {"low", "moderate", "high"} <= levels
    for t in ("s5", "s3_1", "s6"):
        for _ in range(60):
            p = random_patient(rng, t)
            f = random_form(t, rng, p)
            if "p_jhfrat" in f:
                assert f["p_jhfrat"] >= 14
            if "p_braden" in f:
                assert f["p_braden_risk"] == braden_risk(f["p_braden"])


def test_admission_forms_are_coherent_and_formal_scripts_have_no_questions():
    import random
    from nursing_tts.fake import audit, random_datetime, random_form, random_patient
    from nursing_tts.generator import build_script
    rng = random.Random(13)
    for i in range(250):
        p = random_patient(rng, "s1")
        f = random_form("s1", rng, p)
        assert audit(f, p, "s1") == [], (audit(f, p, "s1"), p.surgery or p.regimen)
        hist = set(f.get("history") or [])
        meds = f.get("medications", "")
        if "인슐린" in meds or "메트포르민" in meds:
            assert "dm" in hist
        if any(w in meds for w in ("암로디핀", "로사르탄", "텔미사르탄")):
            assert "htn" in hist
        s = build_script("s1", f, p, random_datetime(rng), style="formal", seed=i)
        assert "?" not in s.spoken_text, s.spoken_text          # 격식체 문진에 질문 문장 없음
        assert "이었다고" not in s.spoken_text
        assert not any(k.startswith("p_") for k in f)
        if int(f.get("nrs") or 0) == 0:
            assert "더 아프다" not in s.spoken_text and "통증 양상" not in s.spoken_text
        if "응급실" in f.get("chief_complaint", "") + f.get("present_illness", ""):
            assert "외래 통해" not in s.spoken_text and "외래로 입원" not in s.spoken_text and "외래 경유" not in s.spoken_text
        assert "올렸고 잘 드셨" not in s.spoken_text and "SOW" not in s.spoken_text   # post-op diet talk is not admission talk
    rng = random.Random(21)
    allergic = iso = sense = 0
    for _ in range(200):
        p = random_patient(rng, "s1"); f = random_form("s1", rng, p)
        allergic += f.get("allergy") != ["none"]; iso += f.get("isolation") != "none"; sense += f.get("sense") != ["none"]
    assert allergic < 60 and iso < 25 and sense < 80, (allergic, iso, sense)   # rare things stay rare


def test_other_templates_are_coherent():
    """2026-10-17: every template was audited by reading 10+ generated scripts; the contradictions found then
    (POD vs 시점, order vs drug given, 금식 vs 물 시작, PCA 제거 vs 재사정, 존스홉킨스 for a walking 34-year-old …)
    must not come back.  Only the progress record (S6) carries the charting checklist."""
    import random
    from nursing_tts.fake import audit, random_datetime, random_form, random_patient
    from nursing_tts.generator import build_script
    rng = random.Random(31)
    for t in ("s2", "s3_1", "s3_2", "s4", "s5", "s6"):
        for i in range(60):
            p = random_patient(rng, t)
            f = random_form(t, rng, p)
            assert audit(f, p, t) == [], (t, audit(f, p, t))
            assert t == "s6" or not any(k.startswith("p_") for k in f), t
            text = build_script(t, f, p, random_datetime(rng), style="formal", seed=i).spoken_text.replace("\n", " ")
            assert "?" not in text and "FLACC" not in text and "하퇴 절단술" not in text, text
            m = re.search(r"(\S{2,}) \1\b", text)
            assert not m or m.group(1) in ("하루", "두", "번", "자주", "조금"), (t, m.group(0))
            if t == "s2":
                assert f["op_date"].startswith(f"내일 {p.op_date}"), f["op_date"]
                assert "복부 JP" not in text and "항경련제" not in text and "prep_detail" not in f
            if t == "s3_1":
                assert {"day0": 0, "pod1": 1, "pod2": 2}[f["timing"]] == p.pod
                assert (f["o2"] == "none") == (f["vitals"]["o2"] == "room air")
                if f["consciousness"] == "drowsy":
                    assert not f.get("responds") and not f.get("pca_edu")
                if f["timing"] != "day0":
                    assert "arrival_time" not in f and f["breathing"] == "inspirometer"
            if t == "s3_2":
                ev, v = f["event"], f["vitals"]
                assert f["noti_content"].startswith(f"BT {v['bt']}, BP {v['sbp']}/{v['dbp']}, HR {v['hr']}")
                if ev == "발열":
                    assert v["bt"] >= 37.8
                if ev == "통증":
                    assert f["nrs"] >= 6 and "pain_med" not in f
                if ev not in ("출혈", "배액 이상"):
                    assert f["recheck"] == "na"
                if f.get("med_given", "").endswith("PO"):
                    assert "PO" in f["orders"] or "주스" in f["med_given"], (f["orders"], f["med_given"])
            if t == "s4":
                assert f["er_edu"] == ("chemo" if p.kind == "chemo" else "op")
                assert "referral" not in f or "stoma" not in f["referral"] or f.get("device") != "stoma"
            if t == "s5":
                if f.get("diet") == "npo":
                    assert f.get("gas_out") is False
                if f.get("diet") in ("sd", "gd", "soft", "dm"):
                    assert "gas_out" not in f
                if p.kind != "chemo" and f.get("glucose"):
                    assert "dm" in f["history"]
                if p.kind != "chemo" and (p.pod or 0) >= 4:
                    assert f.get("pain_mgmt") not in ("pca", "pca_prn")
            if t == "s6":
                if f["reassess"] != "stable":
                    assert f["nrs4"] < f["nrs1"]
                if f["reassess"] == "after_pca":
                    assert f["pca_remove"] == "removed"
                if f["meal1"] == "npo":
                    assert f["meal2"] == "npo"


def test_fall_history_follows_the_admission_and_each_register_has_several_endings():
    """2026-10-17: 낙상력 is asked in the interview and is 'yes' when the patient came in after a fall (JHFRAT +5);
    every register offers several real endings for one phrase (하였습니다/했습니다/드렸습니다, 고요/구요, 함/하였음)."""
    import random
    from nursing_tts import phrase_store
    from nursing_tts.fake import random_form, random_patient, jhfrat_score
    rng = random.Random(8)
    seen_yes = 0
    for _ in range(300):
        p = random_patient(rng, "s1"); f = random_form("s1", rng, p)
        cc = f.get("chief_complaint", "") + f.get("present_illness", "")
        if any(w in cc for w in ("낙상", "미끄러", "넘어")):
            assert f["fall_history"] == "yes", cc
            seen_yes += 1
        forced_high = p.scenario in ("THA", "BKA", "Tracheostomy")   # the scenario forces 고위험 (score raised to 14+)
        assert f["jhfrat"] == jhfrat_score(f, p) or (forced_high and f["jhfrat"] >= 14), (p.scenario, f["jhfrat"], jhfrat_score(f, p))
    assert seen_yes >= 5
    endings = {}
    for style in ("formal", "casual", "chart"):
        endings[style] = {phrase_store.stylize("보호자분께 수술 대기실 위치 설명하였습니다.", random.Random(i), style, expand=True).rsplit(" ", 1)[-1] for i in range(200)}
    assert len(endings["formal"]) >= 3 and len(endings["casual"]) >= 4 and len(endings["chart"]) >= 2, endings
    assert "설명드렸습니다." in endings["formal"] and "설명했구요," in endings["casual"] and "설명하였음." in endings["chart"]
