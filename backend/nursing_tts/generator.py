"""Turns a filled template form into a spoken narrative (+ TTS text + JSON)."""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from . import korean
from .grammar import close_sentence, fix_josa
from . import phrase_store
from . import signal as signal_mod
from .templates.extra_phrases import VITALS_FORMS
from .templates import get_template
from .templates.base import Field, RecordTemplate

# ---------------------------------------------------------------------------
# Patient / context
# ---------------------------------------------------------------------------

SURGERY_KO = {
    "Laparoscopic total gastrectomy": "복강경 위전절제술",
    "Laparoscopic subtotal gastrectomy": "복강경 위아전절제술",
    "Laparoscopic distal gastrectomy": "복강경 원위부 위절제술",
    "Laparoscopic right hemicolectomy": "복강경 우측 결장절제술",
    "Laparoscopic anterior resection": "복강경 전방절제술",
    "Laparoscopic low anterior resection": "복강경 저위전방절제술",
    "Laparoscopic cholecystectomy": "복강경 담낭절제술",
    "Laparoscopic appendectomy": "복강경 충수절제술",
    "Open hemicolectomy": "개복 결장절제술",
    "Lobectomy": "폐엽절제술",
    "Mastectomy": "유방절제술",
    "Total knee replacement arthroplasty": "슬관절 전치환술",
    "Total hip replacement arthroplasty": "고관절 전치환술",
    "Hysterectomy": "자궁절제술",
    "PPPD": "유문보존 췌십이지장절제술",
    "Hepatectomy": "간절제술",
    "Thyroidectomy": "갑상선절제술",
    "ORIF ankle": "발목 골절 관혈적 정복 및 내고정술",
    "Shoulder arthroplasty": "어깨 관절 치환술",
    "Total laparoscopic hysterectomy": "복강경 전자궁절제술",
    "Cataract surgery": "백내장 수술",
}

SURGERY_ABBR = {
    "Laparoscopic total gastrectomy": "TG",
    "Laparoscopic subtotal gastrectomy": "STG",
    "Laparoscopic distal gastrectomy": "DG",
    "Laparoscopic right hemicolectomy": "Rt. hemicolectomy",
    "Laparoscopic anterior resection": "AR",
    "Laparoscopic low anterior resection": "LAR",
    "Laparoscopic cholecystectomy": "lapa chole",
    "Laparoscopic appendectomy": "lapa appe",
    "Total knee replacement arthroplasty": "TKRA",
    "Total hip replacement arthroplasty": "THRA",
    "ORIF ankle": "ankle ORIF",
    "Total laparoscopic hysterectomy": "TLH",
}


from .clinical import SURGERY_ABBR as _KB_ABBR, SURGERY_KO as _KB_KO  # ward scenarios (clinical.py)

SURGERY_KO.update(_KB_KO)
SURGERY_ABBR.update(_KB_ABBR)


@dataclass
class Patient:
    name: str = "홍길동"
    age: int | None = 64
    sex: str = "남"            # 남 / 여
    diagnosis: str = "위암"
    surgery: str = "Laparoscopic total gastrectomy"
    professor: str = "김민수"
    department: str = "외과"
    pod: int | None = 2
    op_date: str = ""          # "10월 14일"
    admission_date: str = ""   # "10월 13일"
    kind: str = "op"           # op | chemo (chemotherapy admission: no surgery, cycle/day instead of POD)
    regimen: str = ""          # e.g. "mFOLFOX6"
    cycle: int | None = None   # 항암 n차
    day: int | None = None     # D1, D2 ... (regimen day: the infusion day of this admission)
    scenario: str = ""         # clinical.py key the patient was drawn from
    hod: int | None = None     # 항암 입원 일차 HOD#1 입원 → HOD#2 항암(=D day) … (user 2026-10-18)

    def context(self, rng: random.Random) -> dict[str, Any]:
        chemo = self.kind == "chemo"
        surg_ko = SURGERY_KO.get(self.surgery, self.surgery)
        surg_abbr = SURGERY_ABBR.get(self.surgery, "")
        cands = [s for s in [self.surgery, surg_ko, surg_abbr] if s]
        surgery_spoken = rng.choice(cands) if cands else ""
        if chemo:
            treatment = f"{self.regimen} 항암"
            treatment_ko = treatment  # nurses say the regimen name, not the drug list
            treatment_abbr = self.regimen
            stage = (f"{self.cycle}차 HOD {self.hod}" if self.cycle else f"HOD {self.hod}") if self.hod else \
                (f"{self.cycle}차 D{self.day}" if self.cycle else f"D{self.day or 1}")  # follows "<regimen> 항암"
            surgery_spoken = treatment
        else:
            treatment, treatment_ko, treatment_abbr = surgery_spoken, surg_ko, surg_abbr or surg_ko
            stage = f"POD {self.pod}" if self.pod is not None else ""
        return {
            "name": self.name,
            "age": self.age if self.age is not None else "",
            "sex": "남자" if self.sex.startswith("남") else "여자",
            "sex_short": self.sex,
            "dx": self.diagnosis,
            "surgery": surgery_spoken,
            "surgery_en": self.surgery if not chemo else treatment,
            "surgery_ko": surg_ko if not chemo else treatment_ko,
            "surgery_abbr": (surg_abbr or surg_ko) if not chemo else treatment_abbr,
            "treatment": treatment,          # surgery (spoken) or "<regimen> 항암"
            "treatment_ko": treatment_ko,
            "treatment_abbr": treatment_abbr,
            "stage": stage,                  # "POD 2" or "3차 HOD 2"
            "regimen": self.regimen,
            "cycle": self.cycle if self.cycle is not None else "",
            "day": self.day if self.day is not None else "",
            "hod": self.hod if self.hod is not None else "",
            "prof": self.professor,
            "dept": self.department,
            "pod": self.pod if self.pod is not None else "",
            "op_date": self.op_date,
            "admission_date": self.admission_date,
            "med_teach": "약 복용법과 ",     # S4 teach-back; build_script blanks it when no drug was given or taken
        }


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class Script:
    spoken_text: str
    tts_text: str
    signal: str
    sentences: list[str]
    structured: dict[str, Any] = field(default_factory=dict)
    seed: int = 0
    turns: list[dict[str, str]] = field(default_factory=list)   # [{"speaker": nurse|patient, "text"}] — one per line of spoken_text


# ---------------------------------------------------------------------------
# Signal line
# ---------------------------------------------------------------------------

def signal_line(when: datetime, patient_name: str, kind: str, fmt: str = "strict", rng: random.Random | None = None,
                use_aliases: bool = False) -> tuple[str, str, str]:
    """Return (written, tts, format_key).  Default is the mandatory spec form:
    「2026년 10월 5일 오전 10시 30분 홍길동 님 간호정보조사 기록입니다.」"""
    custom = phrase_store.get_override("_signal", "formats", "phrases")
    templates = [t for t in custom if "{name}" in t] if custom else None
    return signal_mod.render(when, patient_name, kind, fmt, rng, use_aliases, templates)


# ---------------------------------------------------------------------------
# Vitals realizer (shared by several templates)
# ---------------------------------------------------------------------------

def _vf(key: str) -> list[str]:
    return phrase_store.effective("_vitals", key, "phrases", VITALS_FORMS[key])


def realize_vitals(value: dict[str, Any], rng: random.Random, verb_style: str = "mixed", remeasure: bool = False) -> str:
    """value: {sbp, dbp, hr, rr, bt, spo2, o2}"""
    parts: list[str] = []
    v = dict(value)
    if v.get("bt"):
        v["bt_casual"] = korean.temperature_casual(float(v["bt"]))
    slang = ("샛", "비피", "새츄레이션", "HR는", "RR은", "PR ")
    vf = (lambda key: [f for f in _vf(key) if not any(s in f for s in slang)] or _vf(key)) if verb_style in ("formal", "chart") else _vf
    if v.get("sbp") and v.get("dbp"):
        parts.append(rng.choice(vf("bp")).format(**v))
    if v.get("hr"):
        parts.append(rng.choice(vf("hr")).format(**v))
    if v.get("rr"):
        parts.append(rng.choice(vf("rr")).format(**v))
    if v.get("bt"):
        bt_forms = [f for f in _vf("bt") if verb_style not in ("formal", "chart") or "bt_casual" not in f]   # "열 7도 4" is ward slang, not 격식체/기록체
        parts.append(rng.choice(bt_forms or _vf("bt")).format(**v))
    if v.get("spo2"):
        base = rng.choice(vf("spo2")).format(**v)
        o2 = str(v.get("o2") or "")
        if o2 and o2 not in ("room air", "none", ""):
            base = rng.choice(_vf("o2_with")).format(base=base, o2=o2)
        elif o2 == "room air":
            base = rng.choice(_vf("o2_room")).format(base=base)
        parts.append(base)
    if not parts:
        return ""
    lead = rng.choice(_vf("lead"))
    no_check = bool(re.search("체크|측정", lead)) or remeasure   # "체크하니 … 체크되었습니다", "재측정 … 측정되었습니다"
    if lead.endswith(("은 ", "는 ")):   # "바이탈은 혈압은 …" — one topic marker is enough
        parts[0] = re.sub(r"^(\S+?)(은|는) ", r"\1 ", parts[0])
    joiner = rng.choice([", ", ", ", " "])
    if verb_style == "chart":
        endings = ["측정됨.", "체크됨.", "확인됨.", "임."]
    else:
        endings = _vf("ending_formal") if verb_style == "formal" else _vf("ending")
    ending = rng.choice([e for e in endings if not (no_check and re.search("체크|측정", e))] or endings)
    body = joiner.join(parts)
    sep = "" if ending.startswith(("입니다", "이고", "임")) else " "   # "체온 37.0입니다", not "37.0 입니다"
    return f"{lead}{body}{sep}{ending}".replace("  ", " ")


# ---------------------------------------------------------------------------
# Field realizers
# ---------------------------------------------------------------------------

_CONNECTIVE_ENDINGS = ("구요,", "고요,", "고,", "며,", "하고,", "이며,", "지만,", "으며,", "이고,", "되고,")


def _close(fragment: str, style: str) -> str:
    """close_sentence in the record's own register: 기록체 "사별하심.", not "…없습니다." (2026-10-18 2차 검수)."""
    text = close_sentence(fragment)
    return phrase_store.chart_form(text) if style == "chart" else text


def _is_connective(phrase: str) -> bool:
    return phrase.rstrip().endswith(",")


def _fmt(phrase: str, ctx: dict[str, Any]) -> str:
    try:
        return phrase.format(**ctx)
    except (KeyError, IndexError):
        # leave unknown placeholders intact rather than crash
        return re.sub(r"\{(\w+)\}", lambda m: str(ctx.get(m.group(1), m.group(0))), phrase)


def _finish(phrase: str | None, local: dict[str, Any], rng: random.Random, style: str, force_close: bool) -> str | None:
    """Format placeholders, then derive the register (formal / ~고요, / ~어요.)."""
    if phrase is None:
        return None
    text = _fmt(phrase, local)
    text = phrase_store.stylize(text, rng, style, allow_connective=not force_close)
    if force_close and _is_connective(text):
        text = close_sentence(text)
        if style == "chart":
            text = phrase_store.chart_form(text)
    return text


_PAREN = re.compile(r"\((?!.\))")


_QUOTED = re.compile(r"[다라]고 (하|함|표현|호소|말)")


def _choose(variants: list[str], rng: random.Random, style: str, force_close: bool, mute: bool = False) -> str | None:
    if not variants:
        return None
    pool = variants
    if style in ("formal", "chart"):
        pool = [v for v in variants if not _is_connective(v)] or variants
    if style == "chart":
        pool = [v for v in pool if "거는" not in v] or pool   # "확인할 거는 …임" is speech, not chart (2026-10-18)
    pool = [v for v in pool if "?" not in v] or pool   # no self-asked questions in any record: the dialogue type asks (user 2026-10-18)
    # parenthetical checklist forms "사정함(부위, 점수)" read badly aloud in every style, 기록체 included (2026-10-17 대량 검수:
    # "수면양상을 관찰함(특이사항 없이 잘 잤다고 함)"); "(이)/(으)" particle markers are not parentheses
    pool = [v for v in pool if not _PAREN.search(v)] or pool
    if mute:   # a fresh tracheostomy cannot say "아프다고 하십니다" (2026-10-18 2차 검수: 기관절개 POD 1 "통증 때문에 잠 못 잤다고 함")
        pool = [v for v in pool if not _QUOTED.search(v)] or pool
    if force_close:
        closed = [v for v in pool if not _is_connective(v)]
        if closed:
            pool = closed
    choice = rng.choice(pool)
    if style in ("formal", "chart"):
        choice = re.sub(r"(고요|구요),$", "고,", choice)   # a field whose variants are all 현장체 run-ons still reads 격식체
    if force_close and _is_connective(choice):
        choice = close_sentence(choice)
    return choice


def realize_field(f: Field, value: Any, ctx: dict[str, Any], rng: random.Random, style: str,
                  force_close: bool) -> str | None:
    """Return one spoken fragment for this field, or None if nothing to say."""
    if value is None or value == "" or value == [] or value is False and f.kind != "bool":
        return None
    local = dict(ctx)
    local["unit"] = f.unit
    if f.kind == "select":
        if value in f.skip_values:
            return None
        option = next((o for o in f.options if o.value == value), None)
        if option is None:
            return None
        phrase = _choose(phrase_store.effective(ctx.get("_template", ""), f.key, option.value, option.phrases), rng, style, force_close, bool(ctx.get("_mute")))
        if phrase is None:
            return None
        local["v"] = option.label
        return _finish(phrase, local, rng, style, force_close)
    if f.kind == "multi":
        values = [v for v in value if v not in f.skip_values]
        tk = ctx.get("_template", "")
        if not values or values == ["none"]:
            phrase = _choose(phrase_store.effective(tk, f.key, "none", f.none_phrases), rng, style, force_close, bool(ctx.get("_mute")))
            return _finish(phrase, local, rng, style, force_close)
        options = [o for o in f.options if o.value in values and o.value != "none"]
        # Each option may have its own full phrase; otherwise use the list form.
        nouns = [_fmt(rng.choice(o.nouns), ctx) if o.nouns else o.label for o in options]   # "{allergy_food}"
        if len(nouns) > 1:
            short = all(len(n) <= 6 for n in nouns) and len(nouns) <= 3
            if style in ("formal", "chart"):
                joiner = rng.choice([", ", "(과)와 "]) if short and len(nouns) == 2 else ", "
            else:
                joiner = rng.choice([", ", ", ", "하고 ", "(이)랑 "]) if short else ", "
                if joiner == "하고 " and any(re.search(r"(안|울|험|족|함|약)$", n) for n in nouns[:-1]):
                    joiner = ", "         # "불안하고 지식 부족" reads as the adjective 불안하다 (2026-10-18)
            local["v"] = joiner.join(nouns)
        else:
            local["v"] = nouns[0] if nouns else ""
        local["count"] = len(nouns)
        phrase = _choose(phrase_store.effective(tk, f.key, "phrases", f.phrases), rng, style, force_close, bool(ctx.get("_mute")))
        return _finish(phrase, local, rng, style, force_close)
    if f.kind == "number":
        if rng.random() > f.speak_prob:
            return None
        v = value
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        local["v"] = v
        pool = phrase_store.effective(ctx.get("_template", ""), f.key, "phrases", f.phrases)
        if f.key.startswith("nrs") and v == 0:
            pool = [p for p in pool if "호소" not in p and "아픈 정도" not in p and "정도" not in p] or pool
        if f.key.startswith("nrs") and isinstance(v, int) and v >= 4:   # "NRS 6점으로 조절되고 있습니다" is not controlled
            pool = [p for p in pool if "조절" not in p] or pool
        phrase = _choose(pool, rng, style, force_close, bool(ctx.get("_mute")))
        return _finish(phrase, local, rng, style, force_close)
    if f.kind == "text":
        if rng.random() > f.speak_prob:
            return None
        local["v"] = str(value).strip()
        if f.key in ("lab", "course") and re.search(r"(시행|처방|제거|교체|중단|연계|진행|유지)$", local["v"]):
            local["v"] += "함"   # "…수혈 1 pack 시행" → "…시행하였습니다", not "…시행입니다" (typed or imported values)
        # Nominalised free text ("…옅어지고 있음", "…시행함") must not get "입니다" glued on: chart style keeps
        # it as is, spoken styles say it ("…있습니다", "…하였습니다") and then follow the register.
        if re.search(r"(음|됨|함|임|없음|있음|입원|시작|예정|투여|내원|방문|완료|추적|보냄|하심|계심|다치심|\s중)$", local["v"]) or \
                (f.key in ("lab", "course") and re.search(r"(감소|상승|증가|추가|저하|호전|악화|가능|회복|양호|안정)$", local["v"])):   # not "…감소입니다"
            if f.key == "glucose" and not re.match(r"(혈당|BST)", local["v"]):   # the frame is skipped: keep its subject
                local["v"] = "혈당 " + local["v"]
            if f.key == "lab" and not re.match(r"(\S+\s)?\S*(랩|lab|검사|CBC|금일|오늘)", local["v"], re.I):
                local["v"] = rng.choice(["오늘 랩은 ", "랩은 ", "검사 결과 "]) + local["v"]
            if style == "chart":
                return _fmt("{v}.", local)
            return _finish(phrase_store.formal_from_chart(local["v"] + "."), {}, rng, style, force_close)
        pool = phrase_store.effective(ctx.get("_template", ""), f.key, "phrases", f.phrases)
        if f.key == "discharge_date" and "없음" in str(ctx.get("discharge_meds") or ""):
            pool = [p for p in pool if "퇴원약" not in p] or pool   # "퇴원약과 주의사항 교육" + "퇴원약 처방 없습니다" (H/HP)
        if f.key == "medications":   # 인슐린 "복용", 흡입기 "드시고", bid "아침 식후 하나씩" (2026-10-18)
            inject = re.search(r"주사|흡입", local["v"])
            several = re.search(r"bid|tid|hs|주사|흡입", local["v"])
            pool = [p for p in pool if not (inject and re.search(r"복용|드시", p)) and not (several and "식후" in p)] or pool
        phrase = _choose(pool, rng, style, force_close, bool(ctx.get("_mute")))
        return _finish(phrase, local, rng, style, force_close)
    if f.kind == "bool":
        tk = ctx.get("_template", "")
        phrases = phrase_store.effective(tk, f.key, "phrases", f.phrases) if value else phrase_store.effective(tk, f.key, "false", f.false_phrases)
        phrase = _choose(phrases, rng, style, force_close, bool(ctx.get("_mute")))
        return _finish(phrase, local, rng, style, force_close)
    if f.kind == "vitals":
        if not isinstance(value, dict):
            return None
        return realize_vitals(value, rng, verb_style=style, remeasure=f.key == "re_vitals") or None
    if f.kind in ("date", "time"):
        local["v"] = str(value)
        phrase = _choose(f.phrases, rng, style, force_close, bool(ctx.get("_mute")))
        return _fmt(phrase, local) if phrase else None
    return None


# ---------------------------------------------------------------------------
# Narrative assembly
# ---------------------------------------------------------------------------

_PROT_TIMES = ["오전 8시 30분", "오전 8시 45분", "오전 9시", "오전 9시 15분", "오전 9시 30분", "오전 9시 45분", "오전 10시", "오전 10시 15분", "오전 10시 30분",
               "오전 10시 45분", "오전 11시", "오전 11시 15분", "오전 11시 30분", "오전 11시 45분", "오후 12시"]   # Day shift 정규 차팅, before lunch


def _join_fragments(fragments: list[str]) -> str:
    """Glue fragments: connective ones (ending with ',') continue the sentence."""
    out = ""
    for frag in fragments:
        frag = frag.strip()
        if not frag:
            continue
        if not out:
            out = frag
        elif out.endswith(","):
            out += " " + frag
        else:
            out += " " + frag
    if out.endswith(","):
        out = close_sentence(out)
    return fix_josa(out)


def _sentences_from(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def build_script(template_key: str, form: dict[str, Any], patient: Patient, when: datetime,
                 style: str = "mixed", seed: int | None = None,
                 include_closing: bool = True, signal_format: str = "strict", signal_aliases: bool = False,
                 dialogue: bool = False) -> Script:
    """``dialogue`` (S1 only): the items a nurse asks become question/answer turns (patient answers in 존댓말,
    반말 from 80), the chart facts stay nurse narration; every line of spoken_text has a speaker in ``turns``."""
    from . import dialogue as dialogue_mod
    rng = random.Random(seed)
    if seed is None:
        seed = rng.randrange(1, 2**31)
        rng = random.Random(seed)
    template: RecordTemplate = get_template(template_key)
    ctx = patient.context(rng)
    ctx["style"] = style
    ctx["_template"] = template.key
    # the earlier part of the day as the handover shift says it (2026-10-18 검수: "데이 때 열 났었고" at the 07:00 handover)
    hour = when.hour if when else 15
    ctx["earlier"] = "새벽에" if hour < 12 else "오전에" if hour < 20 else "데이 때"
    if patient.kind != "chemo" and patient.pod == 0:
        ctx["earlier"] = "병실 올라온 뒤"         # the op day: the patient was in the OR during the day
    ctx["_mute"] = patient.scenario == "Tracheostomy" and template_key in ("s3_1", "s3_2", "s5", "s6") and (patient.pod or 0) <= 6
    if template_key == "s4" and "없음" in str(form.get("discharge_meds") or "없음") and form.get("home_meds") in (None, "none"):
        ctx["med_teach"] = ""        # no discharge drug, no home drug: "약 복용법 이해" has nothing to refer to (2026-10-18 H 퇴원)
    # Scalar form values are available as placeholders too ({event}, {bt_peak}, ...).
    # Select values map to their option label; multi values to a comma list of nouns.
    fmap = template.field_map()
    for k, v in form.items():
        f = fmap.get(k)
        if isinstance(v, list) and f is not None and f.kind == "multi":
            nouns = [next((o.nouns[0] if o.nouns else o.label) for o in f.options if o.value == x) for x in v if any(o.value == x for o in f.options)]
            if nouns:
                ctx.setdefault(k, ", ".join(nouns))
            continue
        if isinstance(v, (str, int, float)) and not isinstance(v, bool):
            if isinstance(v, float) and v.is_integer():
                v = int(v)
            if f is not None and f.kind == "select":
                o = next((o for o in f.options if o.value == v), None)
                ctx.setdefault(k, o.label if o else v)
            else:
                ctx.setdefault(k, v)
    # Defaults for detail fields that were left empty, so phrases never show raw braces
    for k, f in fmap.items():
        if k in ctx or f.default is None or isinstance(f.default, (dict, bool)):
            continue
        if isinstance(f.default, list):
            if f.kind == "multi":
                nouns = [next((o.nouns[0] if o.nouns else o.label) for o in f.options if o.value == x) for x in f.default if any(o.value == x for o in f.options)]
                if nouns:
                    ctx[k] = ", ".join(nouns)
            continue
        o = next((o for o in f.options if o.value == f.default), None) if f.kind == "select" else None
        ctx[k] = o.label if o else f.default

    kind = template.signal_kind
    if kind == "경과기록":   # 2026-10-18 사용자: 다음 날부터는 경과기록, 수술 후 경과기록·항암 후 경과기록으로
        kind = "항암 후 경과기록" if patient.kind == "chemo" else "수술 후 경과기록"
    ctx["progress_kind"] = kind
    sig_written, sig_tts, sig_key = signal_line(when, patient.name, kind, signal_format,
                                                random.Random(seed + 3), signal_aliases)
    paragraphs: list[str] = [sig_written]
    tts_paragraphs: list[str] = [sig_tts]
    speakers: list[str] = ["nurse"]
    dialogue = bool(dialogue) and template.key == "s1"
    if template_key == "s6" and form.get("night_onset") in ("asleep", "hypnotic"):   # manual forms too: nobody is woken
        form = {k: v for k, v in form.items() if k not in ("vitals_night", "nrs_n")}  # for 23시 vitals or a pain score
    if dialogue:                                            # a patient who just answered every question is alert, oriented and speaks
        form = dict(form)
        form["consciousness"] = "alert"
        if "orientation" in form:
            form["orientation"] = "yes"
        if any(x in (form.get("sense") or []) for x in ("speech", "foreign")):
            form["sense"] = [x for x in form["sense"] if x not in ("speech", "foreign")] or ["none"]
    asked: set[str] = set()
    pending_ack = ""
    deferred: list[str] = []          # dialogue: chart facts the nurse records after the interview, not between questions (user 2026-10-17)

    intros = phrase_store.effective(template.key, "intros", "phrases", template.intros)
    if patient.kind == "chemo" and ((patient.hod or 2) == 1 or (patient.hod == 2 and hour < 12)):
        intros = [x for x in intros if "시행하고" not in x] or intros   # HOD#1, 07시 HOD#2: the infusion is still ahead (2026-10-18)
    if intros:
        intro = fix_josa(_fmt(rng.choice(intros), ctx)).strip()
        if intro:
            paragraphs.append(intro)
            speakers.append("nurse")
    if dialogue:                                            # "어떻게 오셨어요?" → patient's story → nurse's chart-language summary
        for sp, text in dialogue_mod.opening(form, patient, rng):
            paragraphs.append(text)
            speakers.append(sp)

    structured: dict[str, Any] = {}
    prot_i = 0
    for section in template.sections:
        fragments: list[str] = []
        spoken_fields = [(f, form.get(f.key)) for f in section.fields]
        spoken_fields = [(f, v) for f, v in spoken_fields if v not in (None, "", [], {})]
        turns_here: list[tuple[str, str]] = []
        if dialogue:
            narrated = []
            for f, v in spoken_fields:
                if f.key in dialogue_mod.SKIP_IN_DIALOGUE or f.key in dialogue_mod.COVERED_BY_OPENING:
                    if f.key in dialogue_mod.COVERED_BY_OPENING:
                        structured.setdefault(section.key, {})[f.key] = v
                    continue
                qa_turns = dialogue_mod.qa(f.key, form, patient, rng, asked)
                if qa_turns is None:
                    narrated.append((f, v))
                    continue
                turns_here += qa_turns
                structured.setdefault(section.key, {})[f.key] = v
                if qa_turns[-1][0] == "patient":              # no ack after an education / follow-up line
                    a = dialogue_mod.ack(rng)
                    if a:
                        turns_here.append(("nurse", a))
            spoken_fields = narrated
        # Force the last fragment of a section to close its sentence.
        said: list[Field] = []
        for idx, (f, v) in enumerate(spoken_fields):
            is_last = idx == len(spoken_fields) - 1
            frag = realize_field(f, v, ctx, rng, style, force_close=is_last)
            if frag:
                fragments.append(frag)
                said.append(f)
                structured.setdefault(section.key, {})[f.key] = v
            elif is_last and fragments and fragments[-1].endswith(","):
                fragments[-1] = _close(fragments[-1], style)
        if said and all(f.label == "시각" for f in said):   # a clock time alone is no entry (S6 기본 폼의 빈 항암 칸, 2026-10-18 검토)
            fragments = []
            structured.pop(section.key, None)
        # Avoid very long run-on sentences: close every 3rd connective
        run = 0
        for i, frag in enumerate(fragments):
            if frag.endswith(","):
                run += 1
                if run >= 3:
                    fragments[i] = _close(frag, style)
                    run = 0
            else:
                run = 0
        if fragments and section.group == "protocol" and template.key == "s6":
            # 경과기록 = 그날의 기록을 시간대별로 (user 2026-10-17): each checklist entry gets its own clock time after the evening round
            if section.key == "prot_glucose":   # QID BST 06·12·17·21시 (user 2026-10-18): the pre-lunch check at noon
                prot_i = max(prot_i, _PROT_TIMES.index("오후 12시"))
            fragments.insert(0, f"{_PROT_TIMES[min(prot_i, len(_PROT_TIMES) - 1)]} 환자명 {patient.name}.")
            prot_i += 1
        if fragments and dialogue:
            deferred.append(_join_fragments(fragments))
        elif fragments:
            text = _join_fragments(fragments)
            if pending_ack:                                 # "네." answers the patient before the next chart line
                text, pending_ack = f"{pending_ack} {text}", ""
            paragraphs.append(text)
            speakers.append("nurse")
        for sp, text in turns_here:
            if sp == "nurse" and text in dialogue_mod.ACKS:   # "네." joins the next nurse line instead of standing alone
                pending_ack = text
                continue
            if sp == "nurse" and pending_ack:
                text, pending_ack = f"{pending_ack} {text}", ""
            paragraphs.append(text)
            speakers.append(sp)
    pending_ack = ""
    if deferred:                                            # the interview is over: thank the patient, then dictate the chart
        paragraphs.append(rng.choice(["네, 말씀 감사합니다. 확인한 내용 정리해서 기록하겠습니다.", "네, 알겠습니다. 지금까지 확인한 내용 기록하겠습니다.",
                                      "네, 감사합니다. 사정한 내용 정리하겠습니다."]))
        speakers.append("nurse")
        paragraphs += deferred
        speakers += ["nurse"] * len(deferred)

    closings = phrase_store.effective(template.key, "closings", "phrases", template.closings)
    if include_closing and closings:
        # 녹음 공통 원칙 (user 2026-10-17): the mandatory start phrase (signal "strict") goes with the common closing
        # "이상 [기록지 명칭] 마치겠습니다" — each template lists it first; other signal formats keep the varied closings
        closing = template.closings[0] if signal_format == "strict" and template.closings else rng.choice(closings)
        paragraphs.append(fix_josa(_fmt(closing, ctx)))
        speakers.append("nurse")

    # an empty placeholder ("{stage}" when POD is unknown) must not leave "절제술 ." or double spaces
    paragraphs = [re.sub(r"\s+([.,!?])", r"\1", re.sub(r"[ \t]{2,}", " ", p)).strip() for p in paragraphs]
    paragraphs = [re.sub(r"(다시 잰|재측정) (활력징후|V/S|바이탈) 체크하니 ", r"\1 \2 ", p) for p in paragraphs]   # "다시 잰 활력징후 체크하니"
    spoken_text = "\n".join(paragraphs)
    # TTS layer: signal line already phonetic; convert the rest.
    tts_rng = random.Random(seed + 1)
    tts_paragraphs += [korean.to_tts_text(p, tts_rng) for p in paragraphs[1:]]
    tts_text = "\n".join(tts_paragraphs)
    turns = [{"speaker": sp, "text": p} for sp, p in zip(speakers, paragraphs)] if dialogue else []

    return Script(
        spoken_text=spoken_text,
        tts_text=tts_text,
        signal=sig_written,
        sentences=_sentences_from(spoken_text),
        structured={
            "template": template.key,
            "record_kind": template.signal_kind,
            "record_name": ctx["progress_kind"],
            "patient": patient.__dict__,
            "datetime": when.isoformat(timespec="minutes"),
            "style": style,
            "form": form,
            "sections": structured,
            "signal_format": sig_key,
            "signal_parse": signal_mod.parse(spoken_text).to_dict(),
            "dialogue": dialogue,
            "turns": turns,
        },
        seed=seed,
        turns=turns,
    )
