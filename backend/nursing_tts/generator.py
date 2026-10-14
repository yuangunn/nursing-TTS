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

    def context(self, rng: random.Random) -> dict[str, Any]:
        surg_ko = SURGERY_KO.get(self.surgery, self.surgery)
        surg_abbr = SURGERY_ABBR.get(self.surgery, "")
        surgery_spoken = rng.choice([s for s in [self.surgery, surg_ko, surg_abbr] if s])
        return {
            "name": self.name,
            "age": self.age if self.age is not None else "",
            "sex": "남자" if self.sex.startswith("남") else "여자",
            "sex_short": self.sex,
            "dx": self.diagnosis,
            "surgery": surgery_spoken,
            "surgery_en": self.surgery,
            "surgery_ko": surg_ko,
            "surgery_abbr": surg_abbr or surg_ko,
            "prof": self.professor,
            "dept": self.department,
            "pod": self.pod if self.pod is not None else "",
            "op_date": self.op_date,
            "admission_date": self.admission_date,
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


# ---------------------------------------------------------------------------
# Signal line
# ---------------------------------------------------------------------------

def signal_line(when: datetime, patient_name: str, kind: str) -> tuple[str, str]:
    """Return (written, tts) signal: 「2026년 10월 5일 오전 10시 30분 홍길동 님 간호정보조사 기록입니다.」"""
    written = f"{korean.written_date(when.year, when.month, when.day)} {korean.written_time(when.hour, when.minute)} {patient_name} 님 {kind} 기록입니다."
    tts = f"{korean.read_date(when.year, when.month, when.day)} {korean.read_time(when.hour, when.minute)} {patient_name} 님 {kind} 기록입니다."
    return written, tts


# ---------------------------------------------------------------------------
# Vitals realizer (shared by several templates)
# ---------------------------------------------------------------------------

def _vf(key: str) -> list[str]:
    return phrase_store.effective("_vitals", key, "phrases", VITALS_FORMS[key])


def realize_vitals(value: dict[str, Any], rng: random.Random, verb_style: str = "mixed") -> str:
    """value: {sbp, dbp, hr, rr, bt, spo2, o2}"""
    parts: list[str] = []
    v = dict(value)
    if v.get("bt"):
        v["bt_casual"] = korean.temperature_casual(float(v["bt"]))
    if v.get("sbp") and v.get("dbp"):
        parts.append(rng.choice(_vf("bp")).format(**v))
    if v.get("hr"):
        parts.append(rng.choice(_vf("hr")).format(**v))
    if v.get("rr"):
        parts.append(rng.choice(_vf("rr")).format(**v))
    if v.get("bt"):
        parts.append(rng.choice(_vf("bt")).format(**v))
    if v.get("spo2"):
        base = rng.choice(_vf("spo2")).format(**v)
        o2 = str(v.get("o2") or "")
        if o2 and o2 not in ("room air", "none", ""):
            base = rng.choice(_vf("o2_with")).format(base=base, o2=o2)
        elif o2 == "room air":
            base = rng.choice(_vf("o2_room")).format(base=base)
        parts.append(base)
    if not parts:
        return ""
    lead = rng.choice(_vf("lead"))
    joiner = rng.choice([", ", ", ", " "])
    if verb_style == "chart":
        ending = rng.choice(["측정됨.", "체크됨.", "확인됨.", "임."])
    else:
        ending = rng.choice(_vf("ending_formal") if verb_style == "formal" else _vf("ending"))
    body = joiner.join(parts)
    return f"{lead}{body} {ending}".replace("  ", " ")


# ---------------------------------------------------------------------------
# Field realizers
# ---------------------------------------------------------------------------

_CONNECTIVE_ENDINGS = ("구요,", "고요,", "고,", "며,", "하고,", "이며,", "지만,", "으며,", "이고,", "되고,")


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


def _choose(variants: list[str], rng: random.Random, style: str, force_close: bool) -> str | None:
    if not variants:
        return None
    pool = variants
    if style in ("formal", "chart"):
        pool = [v for v in variants if not _is_connective(v)] or variants
    elif style == "casual":
        pool = [v for v in variants if _is_connective(v) or "셨" in v or "시고" in v] or variants
    if force_close:
        closed = [v for v in pool if not _is_connective(v)]
        if closed:
            pool = closed
    choice = rng.choice(pool)
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
        phrase = _choose(phrase_store.effective(ctx.get("_template", ""), f.key, option.value, option.phrases), rng, style, force_close)
        if phrase is None:
            return None
        local["v"] = option.label
        return _finish(phrase, local, rng, style, force_close)
    if f.kind == "multi":
        values = [v for v in value if v not in f.skip_values]
        tk = ctx.get("_template", "")
        if not values or values == ["none"]:
            phrase = _choose(phrase_store.effective(tk, f.key, "none", f.none_phrases), rng, style, force_close)
            return _finish(phrase, local, rng, style, force_close)
        options = [o for o in f.options if o.value in values and o.value != "none"]
        # Each option may have its own full phrase; otherwise use the list form.
        nouns = [rng.choice(o.nouns) if o.nouns else o.label for o in options]
        if len(nouns) > 1:
            short = all(len(n) <= 6 for n in nouns) and len(nouns) <= 3
            joiner = rng.choice([", ", ", ", "하고 ", "(이)랑 "]) if short else ", "
            local["v"] = joiner.join(nouns)
        else:
            local["v"] = nouns[0] if nouns else ""
        local["count"] = len(nouns)
        phrase = _choose(phrase_store.effective(tk, f.key, "phrases", f.phrases), rng, style, force_close)
        return _finish(phrase, local, rng, style, force_close)
    if f.kind == "number":
        if rng.random() > f.speak_prob:
            return None
        v = value
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        local["v"] = v
        phrase = _choose(phrase_store.effective(ctx.get("_template", ""), f.key, "phrases", f.phrases), rng, style, force_close)
        return _finish(phrase, local, rng, style, force_close)
    if f.kind == "text":
        if rng.random() > f.speak_prob:
            return None
        local["v"] = str(value).strip()
        # Nominalised free text ("…옅어지고 있음", "…시행함") must not get "입니다" glued on.
        if re.search(r"(음|됨|함|임|없음|있음)$", local["v"]):
            return _fmt("{v}.", local)
        phrase = _choose(phrase_store.effective(ctx.get("_template", ""), f.key, "phrases", f.phrases), rng, style, force_close)
        return _finish(phrase, local, rng, style, force_close)
    if f.kind == "bool":
        tk = ctx.get("_template", "")
        phrases = phrase_store.effective(tk, f.key, "phrases", f.phrases) if value else phrase_store.effective(tk, f.key, "false", f.false_phrases)
        phrase = _choose(phrases, rng, style, force_close)
        return _finish(phrase, local, rng, style, force_close)
    if f.kind == "vitals":
        if not isinstance(value, dict):
            return None
        return realize_vitals(value, rng, verb_style=style) or None
    if f.kind in ("date", "time"):
        local["v"] = str(value)
        phrase = _choose(f.phrases, rng, style, force_close)
        return _fmt(phrase, local) if phrase else None
    return None


# ---------------------------------------------------------------------------
# Narrative assembly
# ---------------------------------------------------------------------------

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
                 include_closing: bool = True) -> Script:
    rng = random.Random(seed)
    if seed is None:
        seed = rng.randrange(1, 2**31)
        rng = random.Random(seed)
    template: RecordTemplate = get_template(template_key)
    ctx = patient.context(rng)
    ctx["style"] = style
    ctx["_template"] = template.key
    # Scalar form values are available as placeholders too ({event}, {bt_peak}, ...)
    for k, v in form.items():
        if isinstance(v, (str, int, float)) and not isinstance(v, bool):
            if isinstance(v, float) and v.is_integer():
                v = int(v)
            ctx.setdefault(k, v)

    sig_written, sig_tts = signal_line(when, patient.name, template.signal_kind)
    paragraphs: list[str] = [sig_written]
    tts_paragraphs: list[str] = [sig_tts]

    intros = phrase_store.effective(template.key, "intros", "phrases", template.intros)
    if intros:
        intro = fix_josa(_fmt(rng.choice(intros), ctx))
        paragraphs.append(intro)

    structured: dict[str, Any] = {}
    for section in template.sections:
        fragments: list[str] = []
        spoken_fields = [(f, form.get(f.key)) for f in section.fields]
        spoken_fields = [(f, v) for f, v in spoken_fields if v not in (None, "", [], {})]
        # Force the last fragment of a section to close its sentence.
        for idx, (f, v) in enumerate(spoken_fields):
            is_last = idx == len(spoken_fields) - 1
            frag = realize_field(f, v, ctx, rng, style, force_close=is_last)
            if frag:
                fragments.append(frag)
                structured.setdefault(section.key, {})[f.key] = v
            elif is_last and fragments and fragments[-1].endswith(","):
                fragments[-1] = close_sentence(fragments[-1])
        # Avoid very long run-on sentences: close every 3rd connective
        run = 0
        for i, frag in enumerate(fragments):
            if frag.endswith(","):
                run += 1
                if run >= 3:
                    fragments[i] = close_sentence(frag)
                    run = 0
            else:
                run = 0
        if fragments:
            paragraphs.append(_join_fragments(fragments))

    closings = phrase_store.effective(template.key, "closings", "phrases", template.closings)
    if include_closing and closings:
        paragraphs.append(fix_josa(_fmt(rng.choice(closings), ctx)))

    spoken_text = "\n".join(paragraphs)
    # TTS layer: signal line already phonetic; convert the rest.
    tts_rng = random.Random(seed + 1)
    tts_paragraphs += [korean.to_tts_text(p, tts_rng) for p in paragraphs[1:]]
    tts_text = "\n".join(tts_paragraphs)

    return Script(
        spoken_text=spoken_text,
        tts_text=tts_text,
        signal=sig_written,
        sentences=_sentences_from(spoken_text),
        structured={
            "template": template.key,
            "record_kind": template.signal_kind,
            "patient": patient.__dict__,
            "datetime": when.isoformat(timespec="minutes"),
            "style": style,
            "form": form,
            "sections": structured,
        },
        seed=seed,
    )
