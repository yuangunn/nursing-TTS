"""Ward scenario knowledge base (clinical.py) stays consistent with the templates and produces clean scripts."""
import random
import re

from nursing_tts import clinical
from nursing_tts.fake import chemo_toxicity, coherent_pool, random_datetime, random_form, random_patient
from nursing_tts.generator import build_script
from nursing_tts.templates import get_template, list_templates

TEMPLATES = ["s1", "s2", "s3_1", "s3_2", "s4", "s5", "s6"]
DEPTS = {"외과", "산부인과", "비뇨의학과", "이비인후과", "정형외과", "성형외과", "혈액종양내과"}


def _fields(tpl):
    return {f.key: f for _, f in get_template(tpl).iter_fields()}


def test_scenarios_reference_real_template_fields_and_options():
    assert len(clinical.OPS) >= 30 and len(clinical.CHEMOS) >= 12
    all_fields = {t: _fields(t) for t in TEMPLATES}
    for sc in clinical.SCENARIOS:
        assert sc.dept in DEPTS and sc.dx and sc.cc and sc.pi and sc.ko and sc.abbr, sc.key
        assert sc.age[0] < sc.age[1] and sc.los[0] <= sc.los[1]
        for raw_key, allowed in sc.form.items():
            if raw_key.startswith("_"):
                continue
            tpl, key = raw_key.split(".", 1) if "." in raw_key else (None, raw_key)
            targets = [all_fields[tpl]] if tpl else [f for f in all_fields.values() if key in f]
            assert targets and all(key in t for t in targets), f"{sc.key}: form key {raw_key} matches no template field"
            for fields in targets:
                f = fields[key]
                if allowed is None or f.kind in ("text", "number", "bool", "vitals"):
                    continue
                valid = {o.value for o in f.options}
                vals = [v for grp in allowed for v in (grp if isinstance(grp, list) else [grp])]
                bad = [v for v in vals if v not in valid]
                assert not bad, f"{sc.key}: {raw_key} has unknown option(s) {bad} (valid: {sorted(valid)})"
        for raw_key in sc.pools:
            tpl, key = raw_key.split(".", 1) if "." in raw_key else (None, raw_key)
            targets = [all_fields[tpl]] if tpl else list(all_fields.values())
            assert any(key in t and t[key].kind == "text" for t in targets), f"{sc.key}: pool {raw_key} is not a text field"


def test_every_scenario_builds_clean_scripts_for_its_templates():
    for sc in clinical.SCENARIOS:
        tpls = TEMPLATES if sc.kind == "op" else ["s1", "s4", "s5", "s6"]
        for t in tpls:
            rng = random.Random(len(sc.key) * 31 + len(t))
            p = random_patient(rng, t, scenario=sc.key)
            assert p.scenario == sc.key
            if sc.kind == "chemo":
                assert p.kind == "chemo" and p.regimen == sc.key and p.pod is None and p.cycle
            form = random_form(t, rng, p)
            s = build_script(t, form, p, random_datetime(rng), style=rng.choice(["mixed", "casual", "formal"]), seed=1)
            assert "{" not in s.spoken_text and "}" not in s.spoken_text, (sc.key, t, s.spoken_text)
            assert "POD" not in s.spoken_text or sc.kind == "op", (sc.key, t, s.spoken_text)
            left = re.findall(r"[A-Za-z0-9]+", s.tts_text)
            assert not left, f"{sc.key}/{t}: {left}"
            if t in ("s3_1", "s4", "s5"):  # the intro names the diagnosis or the treatment
                names = list(sc.dx) + [sc.key, sc.ko, sc.abbr]
                assert any(x in s.spoken_text for x in names), (sc.key, t, s.spoken_text.splitlines()[1])


def test_chemo_patients_never_get_surgical_templates_and_say_cycle():
    rng = random.Random(7)
    for t in ("s2", "s3_1", "s3_2"):
        for _ in range(60):
            assert random_patient(rng, t).kind == "op"
    seen = False
    for _ in range(200):
        p = random_patient(rng, "s5")
        if p.kind == "chemo":
            s = build_script("s5", random_form("s5", rng, p), p, random_datetime(rng), style="mixed", seed=3)
            assert "항암" in s.spoken_text and f"{p.cycle}차 D{p.day}" in s.spoken_text and "POD" not in s.spoken_text
            seen = True
            break
    assert seen


def test_s1_admission_purpose_matches_surgery_or_chemo():
    rng = random.Random(11)
    for sc in clinical.SCENARIOS:   # every toxicity complaint has a toxicity history to go with it
        if sc.kind == "chemo" and any(chemo_toxicity(c) for c in sc.cc):
            assert any(chemo_toxicity(x) for x in sc.pi), sc.key
    for _ in range(400):
        p = random_patient(rng, "s1")
        form = random_form("s1", rng, p)
        if p.kind == "chemo":
            cc, pi = form["chief_complaint"], form["present_illness"]
            tox = chemo_toxicity(cc)
            assert chemo_toxicity(pi) == tox, (cc, pi)                     # 설사로 입원 ↔ "3차 예정" never together
            assert form["purpose"] == ("symptom" if tox else "chemo"), (cc, form["purpose"])
            assert ("onset" in form) == tox, (cc, form.get("onset"))
            assert form["plan"] == (f"{p.regimen} {p.cycle}차 예정" if not tox else form["plan"]), form["plan"]
            if tox:
                assert "차 예정" not in form["plan"]
            sc = clinical.BY_KEY[p.scenario]
            assert 1 <= p.cycle <= sc.form["_cycles"], (p.regimen, p.cycle)
            assert "{" not in cc + pi + form["plan"], (cc, pi)              # every {cycle} placeholder filled
            if "1차 시작" in cc + pi:
                assert p.cycle == 1, (cc, pi, p.cycle)
            if "차 위해 입원" in cc:
                assert f"{p.cycle}차 위해 입원" in cc, (cc, p.cycle)
            continue
        assert form["purpose"] == "op", (p.surgery, form["purpose"])
        if p.kind == "op":
            sc = clinical.BY_KEY[p.scenario]
            plan = form.get("plan", "")
            assert plan in ("", f"{sc.abbr} 예정"), (p.surgery, plan)          # no "복강경 수술 예정" for a THA
            cc = form["chief_complaint"]
            if any(w in cc for w in ("낙상", "미끄러", "넘어", "사고")):
                assert "개월" not in form.get("onset", "") and "년" not in form.get("onset", ""), (cc, form.get("onset"))
            if "검진" in cc or "우연히" in cc:
                assert "onset" not in form, (cc, form.get("onset"))


def test_complaint_and_history_never_contradict_the_diagnosis():
    # every diagnosis has at least one fitting complaint and history, so no scenario falls back to "anything"
    for sc in clinical.SCENARIOS:
        for dx in sc.dx:
            assert coherent_pool(dx, sc.cc), (sc.key, dx, "cc")
            assert coherent_pool(dx, sc.pi), (sc.key, dx, "pi")
    rng = random.Random(5)
    for _ in range(400):
        p = random_patient(rng, "s1")
        f = random_form("s1", rng, p)
        cc, pi, dx = f["chief_complaint"], f["present_illness"], p.diagnosis
        for side, other in (("우측", "좌측"), ("좌측", "우측")):
            if side in dx:
                assert other not in cc and other not in pi, (dx, cc, pi)
        if "골관절염" in dx or "무혈성" in dx:
            assert "낙상" not in cc and "골절" not in pi, (dx, cc, pi)
        if "골절" in dx:
            assert "골관절염" not in pi and "괴사" not in pi, (dx, cc, pi)


def test_lmp_only_for_gynecologic_surgery_patients():
    rng = random.Random(3)
    gyn = other = 0
    for _ in range(400):
        p = random_patient(rng, "s1")
        f = random_form("s1", rng, p)
        if p.kind == "op" and p.department == "산부인과" and p.sex == "여" and p.surgery != "C-sec":
            gyn += 1
            assert "lmp" in f and ("폐경" in f["lmp"]) == (p.age >= 52), (p.surgery, p.age, f["lmp"])
        else:
            other += 1
            assert "lmp" not in f, (p.surgery or p.regimen, p.department, p.sex)
    assert gyn > 10 and other > 10


def test_discharge_record_is_same_day_with_ward_leaflet_education():
    rng = random.Random(21)
    want = {"THA": "탈구", "C-sec": "오로", "Lapa chole": "복대", "Bilateral total thyroidectomy": "목운동", "TKA": "양반다리",
            "TLH c BSO": "통목욕", "Hernioplasty": "치료식", "TSA": "보조기", "AC": "마스크"}
    for key, word in want.items():
        seen = ""
        for _ in range(30):
            p = random_patient(rng, "s4", scenario=key)
            f = random_form("s4", rng, p)
            assert "내일" not in f["discharge_date"] and "모레" not in f["discharge_date"], f["discharge_date"]
            assert "{" not in f["special_edu"]
            seen += f["special_edu"]
            s = build_script("s4", f, p, random_datetime(rng), style="mixed", seed=1)
            assert "퇴원 당일 재교육" not in s.spoken_text and "내일 오전 퇴원" not in s.spoken_text
            assert "예정 예정" not in s.spoken_text and "주치의" not in s.spoken_text and "피부반응검사" not in s.spoken_text, s.spoken_text
            assert not any(k.startswith("p_") for k in f), [k for k in f if k.startswith("p_")]   # no protocol items on discharge
        assert word in seen, (key, word)
