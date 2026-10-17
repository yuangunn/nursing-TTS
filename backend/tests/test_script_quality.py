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
                    assert "PO" in f["orders"] or "경구" in f["orders"] or "주스" in f["med_given"], (f["orders"], f["med_given"])
            if t == "s4":
                assert f.get("report_edu", "chemo" if p.kind == "chemo" else "op") == ("chemo" if p.kind == "chemo" else "op")
                for generic, note in (("wound", "wound_note"), ("diet_edu", "diet_note"), ("activity", "activity_note"), ("device", "device_note")):
                    assert not (f.get(generic) and f.get(note)), (generic, f.get(generic), f.get(note))   # 범주당 한 번
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


def test_progress_record_is_a_timeline_and_postop_record_is_day_zero():
    """user 2026-10-17: 경과기록 reads the day's records in clock order (every entry, checklist items included, starts with a
    time); 수술 후 기록 is always POD 0, right after the patient comes up from the recovery room."""
    rng = random.Random(44)
    for i in range(40):
        p = random_patient(rng, "s6")
        f = random_form("s6", rng, p)
        s = build_script("s6", f, p, random_datetime(rng), style="chart", seed=7000 + i)
        lines = s.spoken_text.splitlines()[1:]
        timed = [l for l in lines if re.match(r"^(오전|오후) \d+시", l)]
        assert len(timed) >= 4, lines
        # every line between the intro and the closing is a timed entry, and the times do not go backwards
        body = [l for l in lines if not l.startswith(("이상", "여기까지", "간호정보조사는")) and "경과기록" not in l]
        assert all(re.match(r"^(오전|오후) \d+시", l) for l in body), body
        def minutes(l):
            m = re.match(r"^(오전|오후) (\d+)시(?: (\d+)분)?", l)
            h = int(m.group(2)) % 12 + (12 if m.group(1) == "오후" else 0)
            return h * 60 + int(m.group(3) or 0)
        ts = [minutes(l) for l in timed]
        assert ts == sorted(ts), timed
    for i in range(30):
        p = random_patient(rng, "s3_1")
        f = random_form("s3_1", rng, p)
        assert p.pod == 0 and f["timing"] == "day0" and f.get("arrival_time")
        s = build_script("s3_1", f, p, random_datetime(rng), style="formal", seed=8000 + i)
        assert "POD 1" not in s.spoken_text and "POD 2" not in s.spoken_text and "병실 도착" in s.spoken_text


def test_postop_record_keeps_observation_and_management_apart():
    """user 2026-10-17 (범주별로 나누고 겹치는 부분은 없애라): the post-op record states each category once — drain/foley
    observation in 'lines', their management education only when the device is there (and not when the surgery-specific
    line already says it), medications in their own category, post-op care by the kind of operation, no twin warnings."""
    rng = random.Random(55)
    care_seen = set()
    for i in range(120):
        p = random_patient(rng, "s3_1")
        f = random_form("s3_1", rng, p)
        has_drain = f.get("drain") not in (None, "", "none")
        assert not (f.get("drain_edu") and not has_drain) and not (f.get("drain_note") and not has_drain)
        assert not (f.get("foley_edu") and f.get("foley") != "keep") and not (f.get("foley_note") and f.get("foley") != "keep")
        assert not (f.get("drain_edu") and f.get("drain_note") and re.search(r"당겨|색 짙", f["drain_note"]))
        assert not (f.get("foley_edu") and f.get("foley_note") and re.search(r"당겨|소변백|제거 예정|관리", f["foley_note"]))
        assert "wound_edu" not in f
        if p.department == "정형외과" and p.surgery in ("TKA", "THA"):
            assert "ipc" in f["postop_care"] and "icebag" in f["postop_care"]
        care_seen |= set(f.get("postop_care") or [])
        s = build_script("s3_1", f, p, random_datetime(rng), style="formal", seed=9000 + i).spoken_text
        assert s.count("드레싱 젖거나") <= 1 and s.count("항구토제") <= 1 and s.count("당겨지지 않") <= 1, s
        if f.get("meds_given"):
            assert "투여" in s
    assert {"ipc", "icebag", "compression"} <= care_seen, care_seen


def test_admission_record_says_each_fact_once():
    """user 2026-10-17 (범주별로 나누고 겹치는 부분은 없애라): the admission record no longer repeats sleep, mobility, intake
    and weight change through the separate screening fields."""
    rng = random.Random(66)
    for i in range(80):
        p = random_patient(rng, "s1")
        f = random_form("s1", rng, p)
        assert "sleep_screen" not in f
        sents = re.split(r"(?<=[.])\s+", build_script("s1", f, p, random_datetime(rng), style="formal", seed=9500 + i).spoken_text)
        body = [x for x in sents if not re.search(r"주호소|주증상|호소로|오셨|기록입니다", x)]   # the complaint may mention sleep or walking
        assert sum(bool(re.search(r"수면|주무|잠들|잠을|잠이", x)) for x in body) <= 1, sents
        assert sum(bool(re.search(r"보행|걸으|보조기|휠체어|워커|부축|거동", x)) and not re.search(r"낙상|교육|간호 문제|간호진단", x) for x in body) <= 1, sents
        assert sum(bool(re.search(r"식사량|식욕|입맛", x)) for x in sents) <= 1, sents
