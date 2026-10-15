"""Ward scenario knowledge base (clinical.py) stays consistent with the templates and produces clean scripts."""
import random
import re

from nursing_tts import clinical
from nursing_tts.fake import random_datetime, random_form, random_patient
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
            assert f"항암 {p.cycle}차 D{p.day}" in s.spoken_text and "POD" not in s.spoken_text
            seen = True
            break
    assert seen
