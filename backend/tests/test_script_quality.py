"""Scripts must not contain combinations a nurse would never chart (found by auditing 280 random scripts)."""
import random
import re
import zlib

from nursing_tts import clinical
from nursing_tts.fake import random_datetime, random_form, random_patient
from nursing_tts.generator import build_script

BAD = {
    "금연 금연": r"금연 금연", "숫자 뒤 이십니다": r"\d(?:\.\d)? ?이십니다", "측정한 측정한": r"(\S+) \1\b",
    "PCA 없이 PCA 교육": r"진통제 없이.*PCA 버튼", "의식 저하인데 대답": r"(stupor|confuse).*적절히 대답",
    "금식인데 식사": r"금식 유지.*(전량|절반) (섭취|드)", "소변줄 없는데 도뇨관 간호": r"소변줄 없이.*(도뇨관 (제거|고정|확인)|회음부)",
    "배액관 없는데 JP": r"배액관 없.*JP \d", "변화 없음 있": r"변화 없음 있", "풀코드": r"풀 ?코드|full code",
    "재사정이 더 아픔": r"통증 (\d+)점으로 (감소|호전)",
    "없음에 어미 붙음": r"없음(하여|으로|이고|이구요| 나왔)",
    "사물에 존대": r"(거|것) (따로 )?(없|있)으(시|십)",   # "~하신 거 없으시고" (user 2026-10-17): "~한 것 없고"
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
    from nursing_tts.grammar import has_batchim
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
        for word, cop in re.findall(r"반응은 (\S+?)(이었|였)다고", s.spoken_text):   # 호흡곤란이었다고 / 두드러기였다고
            assert (cop == "이었") == bool(has_batchim(word)), s.spoken_text
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
                # the SBAR opens with the measured numbers; a glucose event puts its BST first (2026-10-18)
                assert re.sub(r"^BST \d+mg/dL, ", "", f["noti_content"]).startswith(f"BT {v['bt']}, BP {v['sbp']}/{v['dbp']}, HR {v['hr']}")
                if ev == "발열":
                    assert v["bt"] >= 37.8
                if ev == "통증":
                    assert f["nrs"] >= 6 and "pain_med" not in f
                if ev not in ("출혈", "배액 이상"):
                    assert f["recheck"] == "na"
                if f.get("med_given", "").endswith("PO"):
                    assert "PO" in f["orders"] or "경구" in f["orders"] or "주스" in f["med_given"], (f["orders"], f["med_given"])
            if t == "s4":
                want = "chemo" if p.kind == "chemo" else "nowound" if p.scenario in ("ESS", "TURB") else "op"   # no skin wound to redden
                assert f.get("report_edu", want) == want
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
        kept = f.get("foley") in ("keep", "cbi")                                           # cbi = TURB 3-way irrigation
        assert not (f.get("foley_edu") and not kept) and not (f.get("foley_note") and not kept)
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
        body = [x for x in sents if not re.search(r"주호소|주증상|호소로|오셨|때문에 입원|기록입니다", x)]   # the complaint may mention sleep or walking
        assert sum(bool(re.search(r"수면|주무|잠들|잠을|잠이", x)) for x in body) <= 1, sents
        assert sum(bool(re.search(r"보행|걸으|보조기|휠체어|워커|부축|거동", x)) and not re.search(r"낙상|교육|간호 문제|간호진단", x) for x in body) <= 1, sents
        assert sum(bool(re.search(r"식사량|식욕|입맛", x)) for x in sents) <= 1, sents


def test_progress_record_has_three_duty_roundings_and_its_own_kind():
    """user 2026-10-17: 경과기록 is its own record kind (not 수술후설명) and charts the first regular rounding of Day (07:00),
    Evening (15:00) and Night (23:00) with vitals each time; drain/urine colour is said in English (no 장액혈성/혈성)."""
    from nursing_tts import signal
    rng = random.Random(88)
    for i in range(30):
        p = random_patient(rng, "s6")
        f = random_form("s6", rng, p)
        s = build_script("s6", f, p, random_datetime(rng), style="chart", seed=9100 + i)
        head = s.spoken_text.splitlines()[0]
        assert "수술후설명" not in head and signal.parse(s.spoken_text).kind == "경과기록", head
        lines = s.spoken_text.splitlines()
        for t in ("오전 7시", "오후 3시", "오후 11시"):
            assert any(l.startswith(t) for l in lines), (t, lines)
        rounds = [next(l for l in lines if l.startswith(t)) for t in ("오전 7시", "오후 3시", "오후 11시")]   # 07:40 PRN 재사정은 라운딩 아님
        assert all(re.search(r"혈압|BP|활력|V/S|VS|바이탈", l) for l in rounds), rounds
        assert not re.search(r"장액혈성|(?<!무)혈성", s.spoken_text) and "serosanguineous" not in s.tts_text and "bloody" not in s.tts_text
        assert s.spoken_text.splitlines()[-1].startswith(("이상", "여기까지"))


COMMON_CLOSING = {"s1": "이상 간호정보조사지 마치겠습니다.", "s2": "이상 수술전 간호기록 마치겠습니다.", "s3_1": "이상 수술후 간호기록 마치겠습니다.",
                  "s3_2": "이상 수술후 간호기록 마치겠습니다.", "s4": "이상 퇴원 간호기록 마치겠습니다.", "s5": "이상 인계기록지 마치겠습니다.",
                  "s6": "이상 경과기록 마치겠습니다."}


def test_strict_signal_ends_with_the_common_closing():
    """녹음 공통 원칙 (user 2026-10-17): 시작은 「… 님 [기록종류] 기록입니다」, 끝은 「이상 [기록지 명칭] 마치겠습니다」.
    With the mandatory start phrase every record ends with its common closing; the random signal mix keeps varied closings."""
    rng = random.Random(99)
    varied = set()
    for t, closing in COMMON_CLOSING.items():
        for i in range(8):
            p = random_patient(rng, t)
            f = random_form(t, rng, p)
            for dlg in ((False, True) if t == "s1" else (False,)):
                s = build_script(t, f, p, random_datetime(rng), style="formal", seed=9300 + i, signal_format="strict", dialogue=dlg)
                assert s.spoken_text.splitlines()[-1] == closing, (t, dlg, s.spoken_text.splitlines()[-1])
                assert re.search(r"님 \S+ 기록입니다\.$", s.spoken_text.splitlines()[0]), s.spoken_text.splitlines()[0]
            r = build_script(t, f, p, random_datetime(rng), style="formal", seed=9400 + i, signal_format="random")
            varied.add(r.spoken_text.splitlines()[-1])
    assert len(varied) > len(COMMON_CLOSING), varied   # the random mix still varies the closing


def test_record_time_follows_the_patient_timeline():
    """user 2026-10-17 (맥락): the signal date/time sits on the patient's timeline and after the record's own clock — no POD 0
    note months away from its operation or before the ward arrival, no progress note timed before its 23:00 round."""
    from datetime import datetime, timedelta
    from nursing_tts.fake import _month_day, _parse_clock, record_datetime
    now = datetime(2026, 10, 17, 22, 0)
    rng = random.Random(123)

    def same_day(d, md):
        return (d.month, d.day) == md

    for t in ("s1", "s2", "s3_1", "s3_2", "s4", "s5", "s6"):
        for _ in range(25):
            p = random_patient(rng, t)
            f = random_form(t, rng, p)
            w = record_datetime(t, p, f, rng, now=now)
            mins = w.hour * 60 + w.minute
            op = _month_day(p.op_date)
            assert w <= now + timedelta(days=1), (t, w)
            if t == "s1":
                assert same_day(w, _month_day(p.admission_date)), (p.admission_date, w)
                assert (18 * 60 <= mins <= 23 * 60 + 30) if f.get("route") == "er" else (10 * 60 <= mins <= 16 * 60 + 30), (f.get("route"), w)
            if t == "s2":
                assert same_day(w + timedelta(days=1), op) and "내일" in f["op_date"], (p.op_date, w, f["op_date"])
            if t == "s3_1":
                assert same_day(w, op) and mins >= _parse_clock(f["arrival_time"]) + 15, (p.op_date, f.get("arrival_time"), w)
            if t == "s3_2":
                found, again = _parse_clock(f["found_time"]), _parse_clock(f["re_time"])
                if again < found:
                    assert same_day(w - timedelta(days=p.pod + 1), op), (p.op_date, p.pod, w)
                else:
                    late = w.hour < 2 and again >= 22 * 60     # a 23:30 recheck is charted just after midnight
                    assert same_day(w - timedelta(days=p.pod + (1 if late else 0)), op) and (late or mins > again), (p.op_date, p.pod, f["re_time"], w)
            if t == "s4":
                assert 8 * 60 + 30 <= mins <= 10 * 60 + 40, w
                visit = _month_day(f["opd"])
                assert any(same_day(w + timedelta(days=k), visit) for k in range(1, 45)), (w, f["opd"])   # clinic after the discharge
            if t == "s5":
                assert w.hour in (7, 15, 23), w
            if t == "s6":
                assert mins >= _parse_clock(f["t8"]) + 5, (f["t8"], w)


def test_demo_read_through_context_rules():
    """Context errors found by reading the 21 lab-demo scripts end to end (2026-10-17)."""
    from datetime import date
    from nursing_tts.templates import get_template
    # a record-scoped variant stays in its record (common.py options are shared objects)
    s1_alert = next(o for o in get_template("s1").field_map()["consciousness"].options if o.value == "alert").phrases
    s5_alert = next(o for o in get_template("s5").field_map()["consciousness"].options if o.value == "alert").phrases
    assert "멘탈 클리어합니다." in s5_alert and "멘탈 클리어합니다." not in s1_alert
    rng = random.Random(321)
    for i in range(60):
        p = random_patient(rng, "s1")
        f = random_form("s1", rng, p)
        txt = build_script("s1", f, p, random_datetime(rng), style="formal", seed=9600 + i, signal_format="strict").spoken_text
        assert txt.count("지남력") + txt.count("오리엔테이션") <= 1, txt
        assert not re.search(r"(불안|우울)하고 ", txt) and "동의서하고" not in txt, txt     # a noun list, not an adjective
        if "anxiety" in (f.get("nursing_problems") or []):
            assert any(e in (f.get("emotion") or []) for e in ("anxiety", "depression")), (f.get("emotion"), f.get("nursing_problems"))
        if f.get("height") and f.get("weight") and f.get("bmi"):
            assert abs(f["bmi"] - f["weight"] / (f["height"] / 100) ** 2) < 0.15, (f["height"], f["weight"], f["bmi"])
            assert f["height"] >= 157 if p.sex.startswith("남") else f["height"] <= 168, (p.sex, f["height"])
        assert "못 드심 피하도록" not in txt and "아직 안 하신" not in txt, txt
    for i in range(80):
        p = random_patient(rng, "s3_1")
        f = random_form("s3_1", rng, p)
        if f.get("diet_status") == "npo":
            assert f.get("pain_med") != "prn_po", f.get("pain_med")         # 금식(물도 금지)인데 경구 진통제
        assert f.get("foley") != "removed"
        if p.surgery == "RALRP" and f.get("foley") == "keep":
            assert not f.get("foley_edu") and "1~2주" in (f.get("foley_note") or ""), (f.get("foley_edu"), f.get("foley_note"))
        if "에녹사파린" in (f.get("meds_given") or ""):
            assert p.surgery in ("TKA", "THA", "BKA", "ORIF"), p.surgery
    for i in range(80):
        p = random_patient(rng, "s5")
        f = random_form("s5", rng, p)
        drain = f.get("drain") or ""
        m, amounts = re.search(r"(?:Hemovac|JP) (\d+)", f.get("io") or ""), [int(x) for x in re.findall(r"(\d+)\s*cc", drain)]
        if m and amounts:   # every drain counts (2026-10-18: "유방 JP 40cc, 복부 JP 30cc" → I/O "JP 40")
            want = amounts[0] * 2 if "각" in drain and len(amounts) == 1 else sum(amounts)
            assert int(m.group(1)) == want, (f["io"], drain)
        if drain and "제거" not in drain:
            assert not re.search(r"(Hemovac|JP|헤모박|배액관)[^.]*제거", f.get("special") or ""), (drain, f.get("special"))
    for i in range(80):
        p = random_patient(rng, "s4")
        f = random_form("s4", rng, p)
        if p.kind == "chemo" and f.get("next_admission"):
            (om, od), (nm, nd) = [tuple(int(x) for x in re.match(r"(\d+)월 (\d+)일", v).groups()) for v in (p.op_date, f["next_admission"])]
            gap = (date(2026 + (nm < om), nm, nd) - date(2026, om, od)).days
            # the next infusion (weekly K+TC: D8/D15), discharged the morning after (D2/D9/D16; FOLF pump D3), moved off weekends (2026-10-18)
            want = 14 if "FOLF" in p.regimen else {2: 7, 9: 14}.get(p.day, 21) if p.regimen == "K+TC" else 21
            assert want <= gap <= want + 3, (p.regimen, p.day, p.op_date, f["next_admission"])
    for i in range(30):
        p = random_patient(rng, "s2", scenario="ESS")
        f = random_form("s2", rng, p)
        assert not {"shave", "skin_prep"} & set(f.get("prep") or []), f.get("prep")
    for i in range(150):
        p = random_patient(rng, "s1")
        f = random_form("s1", rng, p)
        if "심방세동" in (f.get("history_detail") or ""):
            assert "아픽사반" in f.get("medications", "") and f.get("antiplatelet") in ("stopped", "taking"), (f.get("medications"), f.get("antiplatelet"))
            assert f.get("antiplatelet") != "stopped" or f.get("apt_hold") == "이틀 전"
    for i in range(80):
        p = random_patient(rng, "s4")
        f = random_form("s4", rng, p)
        if "없음" in str(f.get("discharge_meds") or ""):
            assert not f.get("side_effect_edu")
    for i in range(80):
        p = random_patient(rng, "s5")
        f = random_form("s5", rng, p)
        if f.get("pain_mgmt") == "pca_prn":
            assert "트라마돌" not in (f.get("prn") or ""), f.get("prn")
    for i in range(120):
        p = random_patient(rng, "s6")
        f = random_form("s6", rng, p)
        if any(k.startswith("p_temp") for k in f) and f.get("p_temp_measure"):
            assert f.get("p_antipyretic_give") and f.get("p_temp_recheck") and f["bt3"] < 37.5, (f.get("p_temp"), f.get("bt3"))
    for t in ("s6", "s3_2", "s4"):                                              # 격식체 lines carry no 기록체 sentence inside
        for i in range(25):
            p = random_patient(rng, t)
            f = random_form(t, rng, p)
            txt = build_script(t, f, p, random_datetime(rng), style="formal", seed=9700 + i).spoken_text
            assert not re.search(r"(함|됨)\. ", txt), re.findall(r"[^.]*(?:함|됨)\. ", txt)[:3]


def test_styles_do_not_mix_chart_and_spoken_endings():
    """2026-10-17 대량 검수: 격식체에 "잠들어 있음, 특이 호소 없습니다" / "추가적인 중재 원하지 않음." / "수액 잘 들어감.",
    기록체에 "소변 색 맑습니다" / "격리 아닙니다" / "구토 1회 있었습니다" / 체크리스트 괄호 "관찰함(…)"이 남았다."""
    from nursing_tts.phrase_store import chart_form, formal_from_chart
    assert chart_form("소변 색 맑습니다. 격리 아닙니다.") == "소변 색 맑음. 격리 아님."
    assert chart_form("구토 1회 있었습니다.") == "구토 1회 있었음." and chart_form("복부 부드럽습니다.") == "복부 부드러움."
    assert chart_form("다음 근무 때 퇴원 처방 확인 해주시면 됩니다.").endswith("확인 요함.")
    assert formal_from_chart("잠들어 있음, 특이 호소 없음.") == "잠들어 있고, 특이 호소 없습니다."
    assert formal_from_chart("오심 호소함, 식후 오심.") == "오심 호소했고, 식후 오심."      # 오심(구역)은 "오셨습니다"가 아님
    leak = re.compile(r"(않음|들어감|잠듦|낮춤|있음,|없음,|(?<!포)함,|됨,)(?=\s|$)")
    rng = random.Random(1017)
    for t in ("s3_1", "s5", "s6"):
        for style in ("formal", "mixed", "casual", "chart"):
            for i in range(25):
                p = random_patient(rng, t)
                f = random_form(t, rng, p)
                s = build_script(t, f, p, random_datetime(rng), style=style, seed=rng.randrange(1 << 30))
                body = "\n".join(s.spoken_text.splitlines()[2:-1])
                assert not re.search(r"\((?!.\))[^)]*\)", body), body                  # no spoken parentheses
                assert not re.search(r"[0-9%] (입니다|임\.)|room air 에", body), body   # "37.0입니다", "room air에"
                if style == "chart":
                    assert not re.search(r"(습니다|어요|세요)\.(?=\s|$)", body), body
                else:
                    assert not leak.search(body), (style, body)


def test_progress_record_day_is_coherent():
    """2026-10-17 대량 검수(경과기록): 아침 전량 섭취 → 점심 금식, NRS 2에 PRN, "30분 뒤 재사정 예정" 뒤 13:30에야 재사정,
    Routine 체크리스트가 라운딩을 되풀이하며 모순, 해열제 뒤에 노티, 380 혈당을 교육만, 아침 제거한 배액관을 오후에 비움."""
    rng = random.Random(1018)
    for i in range(150):
        p = random_patient(rng, "s6")
        f = random_form("s6", rng, p)
        meals = [f.get(k) for k in ("meal1", "meal2", "meal3")]
        assert all(m in ("npo", "sow") for m in meals) or not any(m in ("npo", "sow") for m in meals), meals
        assert f.get("pain_plan") != "prn" or f["nrs1"] >= 4
        assert ("nrs_prn" in f) == (f.get("pain_plan") == "prn")
        assert not any(k.startswith(("p_sleep", "p_status", "p_meal_check", "p_vs_routine", "p_env_", "p_apain_")) and f[k] is True for k in f)
        if f.get("p_drain_remove"):
            assert "제거" in f.get("drain_note", "")
        if f.get("p_bst"):
            assert f["p_bst_time"] == "식후 2시간" and bool(f.get("p_insulin_give")) == (f["p_bst_value"] >= 200)
        s = build_script("s6", f, p, random_datetime(rng), style="formal", seed=i)
        txt = s.spoken_text
        if "노티" in txt and "해열제" in txt and f.get("p_fever_noti") and f.get("p_antipyretic_give"):
            assert txt.index("노티") < txt.index("acetaminophen"), txt
        if "아침 식사 전량" in txt or "일반식 전량" in txt:
            assert "금식" not in txt.split("일반식 전량")[-1], txt


def test_handover_fits_its_shift_and_its_patient():
    """2026-10-18 대량 검수(인계): POD 0·항암 D1을 07시에(수술 전·주입 전), "데이 때 열"을 07·15시에, 15시에 "오전 외래 CT 이송",
    23시에 "퇴원 교육", PCA·미음·발열 환자에게 퇴원 처방, 보호자 없는데 "보호자 면담", 17세 "배우자 상주", "HTN, 알레르기 없어요",
    40cc/hr인데 수액 1900."""
    from nursing_tts.fake import record_datetime
    rng = random.Random(1019)
    for i in range(200):
        p = random_patient(rng, "s5")
        f = random_form("s5", rng, p)
        w = record_datetime("s5", p, f, rng)
        s = build_script("s5", f, p, w, style=rng.choice(["casual", "mixed", "formal"]), seed=i)
        txt = s.spoken_text
        if p.kind == "chemo" or p.pod == 0:
            assert w.hour != 7, (p.surgery or p.regimen, w)
        if w.hour < 20:
            assert "데이 때" not in txt, txt
        plan = f.get("plan", "")
        if w.hour == 15:
            assert not re.search(r"(?<!내일 )(오전|아침)|내일 (아침|오전)", plan), plan
        if w.hour == 23:
            assert "퇴원 교육" not in plan, plan
        if f.get("pain_mgmt") in ("pca", "pca_prn") or f.get("diet") in ("npo", "sow", "ld") or f.get("vs_summary") == "fever":
            assert "퇴원" not in plan + f.get("pending", ""), (f.get("pain_mgmt"), f.get("diet"), plan, f.get("pending"))
        if f.get("caregiver") == "none":
            assert "보호자 동행" not in txt and "보호자 면담" not in txt, txt
        if (p.age or 50) < 20:
            assert f["caregiver"] == "parent"
        assert not re.search(r"(HTN|DM|고혈압|당뇨|COPD|CKD), 알(레르기|러지) 없", txt), txt
        m = re.search(r"(\d+)\s*cc/hr", f.get("fluid", "")), re.search(r"수액 (\d+)", f.get("io", ""))
        if m[0] and m[1]:
            hours = 24 if w.hour == 7 else 8
            assert abs(int(m[1].group(1)) - int(m[0].group(1)) * hours) <= int(m[0].group(1)) * hours * 0.15 + 50, (f["fluid"], f["io"], w)


def test_preop_and_postop_review_2026_10_18():
    """대량 검수(수술 전·후): "병실 도착" 두 번(100%), 도착 직후 "자가배뇨 중", 소변줄 남기는 수술이 소변줄 없이 옴, "…예정이고 설명",
    A형 Rh- 18%, 보호자 없는데 둘 다 이해, 구토·기면 환자에게 "식이 제한 없이 일반식", 재건 부위 압박 드레싱, 수술 쪽 팔에 IV,
    기관절개 환자 "질문에 적절히 대답"·가스 기준 금식, 사물·증상 존대."""
    rng = random.Random(1021)
    rh_neg = 0
    for i in range(300):
        t = "s3_1" if i % 2 else "s2"
        p = random_patient(rng, t)
        f = random_form(t, rng, p)
        s = build_script(t, f, p, random_datetime(rng), style=rng.choice(["formal", "mixed", "casual", "chart"]), seed=i).spoken_text
        assert not re.search(r"(배액관|드레인|소변줄|이상|구토|오심|팽만|제한|장신구|틀니)(은|는|이|가)?\s?없으(시|십)", s), s
        if t == "s2":
            rh_neg += "Rh-" in s
            assert "예정이고 설명" not in s and "교수님임" not in s, s
            if f.get("waiting") == "absent":
                assert f.get("understanding") != "both"
            continue
        assert s.count("병실 도착") + s.count("병실 올라오") <= 1, s
        assert "자가배뇨 중" not in s and "가스 배출 확인되어" not in s, s
        sc = clinical.BY_KEY.get(p.scenario)
        if sc is not None and "keep" in (sc.form.get("s3_1.foley") or sc.form.get("foley") or []):
            assert f.get("foley") in ("keep", "cbi"), (p.scenario, f.get("foley"))
        if f.get("nausea") in ("nausea", "vomit") or f.get("consciousness") == "drowsy":
            assert "식이 제한 없이" not in s and "식사 가능" not in s, s
        if p.scenario == "Breast reconstruction":
            assert "compression" not in (f.get("postop_care") or [])
        if p.scenario == "Tracheostomy":
            assert "질문에 적절히 대답" not in s and "가스" not in s, s
        side = "우측" if "우측" in p.diagnosis else "좌측" if "좌측" in p.diagnosis else ""
        if side and ("유방" in p.diagnosis or p.department == "유방외과"):
            assert ("Rt" not in f["iv"] and "오른" not in f["iv"]) if side == "우측" else ("Lt" not in f["iv"] and "왼" not in f["iv"]), (p.diagnosis, f["iv"])
    assert rh_neg == 0


def test_event_and_discharge_review_2026_10_18():
    """대량 검수(이벤트·퇴원): 재측정이 투약보다 먼저(저혈당 72%), 38.7 → 36.2를 40분 만에, 통증 재사정에 점수 없음, 혈당 사건에 BST 숫자 없음,
    PCA 없는 수술에 PCA 판단, "오심/구토"·"(손저림)" 낭독, 당일 수술에 POD 3 이벤트; 주말 외래 28%, 항암 D1 오전 퇴원,
    "지참약은 없으십니다", "…가능 설명하였습니다", ESS·TURB에 "상처가 빨개지고"."""
    from datetime import datetime as _dt
    from nursing_tts.fake import _parse_clock, record_datetime
    rng = random.Random(1022)
    for i in range(160):
        p = random_patient(rng, "s3_2")
        f = random_form("s3_2", rng, p)
        sc = clinical.BY_KEY[p.scenario]
        assert p.pod <= max(1, sc.los[1]), (p.scenario, p.pod)
        s = build_script("s3_2", f, p, random_datetime(rng), style=rng.choice(["formal", "mixed", "casual", "chart"]), seed=i).spoken_text
        assert "오심/구토" not in s and "(손저림)" not in s, s
        m = re.match(r"(\S+ \d+시(?: \d+분)?)", f.get("med_given") or "")
        if m:
            med, re_t = _parse_clock(m.group(1)), _parse_clock(f["re_time"])
            assert (re_t - med) % (24 * 60) >= 15, (f["med_given"], f["re_time"])          # the recheck follows the drug
        if f["event"] == "발열" and f.get("response") == "improved":
            assert float(f["vitals"]["bt"]) - float(f["re_vitals"]["bt"]) <= 1.25, (f["vitals"]["bt"], f["re_vitals"]["bt"])
        if f["event"] == "통증":
            assert "re_nrs" in f and f"NRS {f['re_nrs']}점" in s, s
        if f["event"] in ("저혈당", "고혈당"):
            assert "re_bst" in f and f["noti_content"].startswith("BST "), f["noti_content"]
        if not any("pca" in a for a in (sc.form.get("attachments") or [])):
            assert "PCA" not in f.get("judgement", "") + f.get("orders", "") + f.get("complaint", ""), (p.scenario, f.get("judgement"), f.get("orders"))
    rng = random.Random(1023)
    for i in range(160):
        p = random_patient(rng, "s4")
        f = random_form("s4", rng, p)
        w = record_datetime("s4", p, f, rng)
        s = build_script("s4", f, p, w, style=rng.choice(["formal", "mixed", "casual", "chart"]), seed=i).spoken_text
        if p.kind == "chemo":
            assert p.day >= 2, (p.regimen, p.day)                                          # the morning after the infusion
        mo, dd = (int(x) for x in re.match(r"(\d+)월 (\d+)일", f["opd"]).groups())
        visit = _dt(w.year + (1 if (mo, dd) < (w.month, w.day) else 0), mo, dd)
        assert visit.weekday() < 5, (f["opd"], w)                                          # no weekend clinic
        assert "지참약은 없으십니다" not in s and "활동 제한은 없으시고" not in s, s
        assert not re.search(r"(가능|결정됨|줄어듦|보냄|됨) 설명(하였|했|드렸)", s), s
        if p.scenario in ("ESS", "TURB"):
            assert "상처가 빨개지고" not in s, s


def test_second_review_2026_10_18():
    """2차 검수(새 시드로 다시 뽑아 읽기): 여자·배꼽/반흔 탈장에 "음낭 부종", 수술한 팔에 IV, "K 3.3로", "복숭아이구요", "설명드렸.",
    "금지이라고", 손목 골절에 목발·체중 부하, 어깨 보조기 6주인데 "무거운 물건 4주간", 갑상선암에 "보조 항암", 기면인데 식사,
    수혈했는데 랩 정상, "수술로, 첫 수술로", 우측 대장암 마킹, 이벤트의 "정규 라운딩"·"다시 잰 활력징후 체크하니"·재측정 혈압 그대로,
    ESS 출혈에 패킹 관찰 없음, 새벽 1시 복도 보행, "처방 처방", 오후 외래에 8시 30분 공복 채혈, 기록체에 "확인할 거는"."""
    from nursing_tts.fake import _upper_limb, record_datetime
    from nursing_tts.grammar import close_sentence
    from nursing_tts.phrase_store import expand_styles, formal_from_chart
    assert close_sentence("탕 목욕은 금지라고 설명드렸고,") == "탕 목욕은 금지라고 설명드렸습니다."
    assert close_sentence("침상 높이 낮췄고,") == "침상 높이 낮췄습니다."
    assert "금지라고" in formal_from_chart("다리 겹치는 자세는 금지 교육함.")
    assert expand_styles("기저질환은 당뇨입니다.")[1] == "기저질환은 당뇨고요,"
    styles = ["formal", "mixed", "casual", "chart"]
    rng = random.Random(2027)

    def gen(t, i, scenario=None):
        p = random_patient(rng, t, scenario=scenario)
        f = random_form(t, rng, p)
        s = build_script(t, f, p, record_datetime(t, p, f, rng), style=styles[i % 4], seed=i).spoken_text
        assert not re.search(r"\((이|으|을|은|과)\)", s), s                               # every particle marker resolved
        assert not re.search(r"(?<![\d.])[\d.]*[036]로 |(?<![\d.])[\d.]*[124579]으로 ", s), s   # "K 3.3로", "Hb 9.0로"
        assert not re.search(r"(복숭아|새우|당뇨|키위)이(구요|고요|고,)", s), s
        assert not [m for m in re.finditer(r"([가-힣])\.(?=\s|$)", s) if (ord(m.group(1)) - 0xAC00) % 28 == 20], s   # "설명드렸."
        assert "금지이라고" not in s and "처방 처방" not in s and not re.search(r"결정 설명(하였|했|드렸)", s), s
        if styles[i % 4] == "chart":
            assert "확인할 거는" not in s, s
        return p, f, s

    for t in ("s3_1", "s5", "s6"):
        for i in range(60):
            p, f, s = gen(t, i, scenario="Hernioplasty")
            if "음낭" in s:
                assert p.sex.startswith("남") and not re.search("배꼽|반흔", p.diagnosis), (p.sex, p.diagnosis, s)
            for sc_key in ("Rotator cuff repair", "Partial mastectomy c SLNB", "ORIF"):
                p, f, s = gen(t, i, scenario=sc_key)
                side = "우측" if "우측" in p.diagnosis else "좌측" if "좌측" in p.diagnosis else ""
                if side and (sc_key != "ORIF" or _upper_limb(p.diagnosis)):
                    bad = r"(Rt|오른)\S*" if side == "우측" else r"(Lt|왼)\S*"
                    assert not re.search(bad + r"( (arm|hand|forearm))? ?\d\d(G|게이지)", s), (p.diagnosis, s)
    for i in range(80):
        p, f, s = gen("s4", i, scenario=random.Random(i).choice(["ORIF", "Rotator cuff repair", "TSA", "MRND", "Bilateral total thyroidectomy"]))
        if _upper_limb(p.diagnosis):
            assert not re.search(r"목발|체중 부하|보행기|다리 올리기|무거운 (물건은|건|것 들기) 4주간|항응고|리바록사반|에독사반", s), (p.diagnosis, s)
        if "갑상선" in p.diagnosis:
            assert "보조 항암" not in s, s
        body = s.split("\n", 1)[1]                                                    # not the signal line's own clock
        if "8시 30분 채혈" in body:
            assert not re.search(r"\d+월 \d+일 (오후 \d+시|오전 9시)", body), body
        assert len(re.findall(r"무거운", body)) <= 1, body                                 # 활동 교육 한 번 (BTT: 운전·복직 문장과 설명문)
        if "PICC" not in s and "펌프" not in s:
            assert "팔찌" in s, s                                                           # 퇴원 범주 1번은 빠지지 않는다
    for i in range(120):
        p, f, s = gen("s5", i)
        if f.get("consciousness") == "drowsy":
            assert f.get("diet") in (None, "npo"), f.get("diet")
        if f.get("transfusion"):
            assert "Hb" in str(f.get("lab")), f.get("lab")
        if re.search(r"gas out 아직|가스 배출 안 됐", s):
            assert "가스 배출 확인" not in s, s
    for i in range(80):
        sc_key = random.Random(i).choice([None, "Lapa RHC", "Tracheostomy", "Total mastectomy c ALND"])
        p, f, s = gen("s2", i, scenario=sc_key)
        assert not re.search(r"수술로, (첫|두|세|1|2)\S* (번째 )?수술", s), s
        if re.search("대장|결장", p.diagnosis):
            assert "마킹" not in s, s
        if p.scenario == "Tracheostomy":
            assert "필담" in s, s
        if p.scenario == "Total mastectomy c ALND":
            assert "JP" in s, s
    for i in range(160):
        p, f, s = gen("s3_2", i, scenario="ESS" if i % 8 == 0 else None)
        assert "정규 라운딩" not in s and not re.search(r"(다시 잰|재측정) (활력징후|V/S|바이탈) 체크하니", s), s
        if f["event"] != "저혈압":
            assert (f["vitals"]["sbp"], f["vitals"]["dbp"]) != (f["re_vitals"]["sbp"], f["re_vitals"]["dbp"]), (f["vitals"], f["re_vitals"])
        if p.scenario == "ESS" and f["event"] == "출혈":
            assert "비강 패킹 거즈" in s and "체위 변경" not in s, s
        if "배액 양상 더 이상" in s:
            assert f.get("drain"), s
        found = f["found_time"]
        hour = int(re.search(r"(\d+)시", found).group(1)) % 12 + (12 if found.startswith("오후") else 0)
        if hour >= 22 or hour < 6:
            assert not re.search(r"복도 보행|도보로", s), s


def test_second_review_progress_and_postop_2026_10_18():
    """2차 검수(경과기록·수술 후): 잠든 환자에게 통증 점수(70%), 수술한 팔 IV, 재원 기간 넘는 POD, 금식인데 KVO, 기관절개 환자가 말함·일반식,
    BKA 복도 보행, 체크리스트 배액 bilious, 케모포트 없이 케모포트 바늘 통증, ORIF 다른 뼈 상처, 도뇨관 체크리스트 모순, 호흡보조근 사용,
    항암 발열에 "수술 부위", "상완로", "체크하니 … 체크"; 수술 후 "IV는 … IV line", NRS 5~6에 정규 진통제만, 도착 직후 경구 PRN,
    PCA 없는 수술에 PCA, 정답 텍스트 "제이피", 발목 운동·침상 안정 두 번, TURB 방광 세척인데 "16 Fr 맑고 노란색"."""
    from nursing_tts.fake import record_datetime
    quoted = re.compile(r"(?<!이해했)[다라]고 (하|함|호소|말)")
    rng = random.Random(3030)
    for i in range(240):
        sc_key = random.Random(i).choice([None, None, "Tracheostomy", "BKA", "ORIF", "TURB", "Rotator cuff repair"])
        p = random_patient(rng, "s6", scenario=sc_key)
        f = random_form("s6", rng, p)
        s = build_script("s6", f, p, record_datetime("s6", p, f, rng), style=["formal", "mixed", "casual", "chart"][i % 4], seed=i).spoken_text
        sc = clinical.BY_KEY.get(p.scenario)
        if f.get("night_onset") in ("asleep", "hypnotic"):
            assert "nrs_n" not in f, f
        if sc is not None and p.kind != "chemo":
            assert p.pod <= max(1, sc.los[1]), (p.scenario, p.pod)
        if f.get("meal1") in ("npo", "sow"):
            assert "KVO" not in s, s
        if p.scenario == "Tracheostomy":
            assert not quoted.search(s) and "일반식" not in s, s
        if p.scenario == "BKA" and p.pod >= 2:
            assert not re.search(r"복도 보행|병동 한 바퀴 보행", s), s
        if f.get("p_drain_output") and f.get("drain_note") and "제거" not in f["drain_note"]:
            assert f["p_drain_color"] in f["drain_note"], (f["p_drain_color"], f["drain_note"])
        assert not re.search(r"bilious|purulent|Suprapubic|혼탁함, 혼탁 없음|호흡보조근 사용 있음|상완로|체크하니[^.]*체크(되|됨|됩)", s), s
        if p.kind == "chemo":
            assert not ("케모포트 바늘" in s and "케모포트" not in str(f.get("line") or "")), s
            assert not re.search(r"wound culture|수술 부위 발적", s), s
        if p.scenario == "ORIF" and "상완골" in p.diagnosis:
            assert not re.search(r"(쇄골|손목|발목) 수술 부위", str(f.get("wound") or "")), f.get("wound")
        if f.get("reassess") == "after_pca":
            assert int(f["nrs4"]) <= 3, f["nrs4"]
    rng = random.Random(3031)
    for i in range(200):
        sc_key = random.Random(i).choice([None, None, "Tracheostomy", "TURB", "Meniscal repair", "Partial nephrectomy", "ESS"])
        p = random_patient(rng, "s3_1", scenario=sc_key)
        f = random_form("s3_1", rng, p)
        s = build_script("s3_1", f, p, record_datetime("s3_1", p, f, rng), style=["formal", "mixed", "casual", "chart"][i % 4], seed=i).spoken_text
        sc = clinical.BY_KEY.get(p.scenario)
        assert not re.search(r"IV는 [^.,]*IV line|제이피|헤모박", s), s
        assert f.get("pain_med") != "prn_po", f.get("pain_med")                            # nothing by mouth an hour after the OR
        if int(f.get("nrs") or 0) >= 5:
            assert f.get("pain_med") in ("pca", "prn_iv"), (f.get("nrs"), f.get("pain_med"))
        if f.get("pain_med") == "pca":
            assert any("pca" in a for a in (sc.form.get("attachments") or [])), p.scenario
        assert len(re.findall(r"발목 운동", s)) <= 1 and len(re.findall(r"침상 안정", s)) <= 1, s
        if p.scenario == "TURB" and f.get("foley") in ("keep", "cbi"):
            assert f["foley"] == "cbi" and "16 Fr" not in s, s
        if p.scenario == "Tracheostomy":
            assert not quoted.search(s.replace("보호자분께 교육하였고 이해했다고", "")), s
