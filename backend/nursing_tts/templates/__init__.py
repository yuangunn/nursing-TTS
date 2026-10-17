"""Record template registry."""
from __future__ import annotations

import copy

from .base import RecordTemplate
from . import s1_admission, s2_preop, s3_postop, s3_2_event, s4_discharge, s5_handover, s6_progress
from .extra_phrases import EXTRA
from .protocols import protocol_sections

TEMPLATES: dict[str, RecordTemplate] = {
    t.key: t for t in (
        s1_admission.TEMPLATE,
        s2_preop.TEMPLATE,
        s3_postop.TEMPLATE,
        s3_2_event.TEMPLATE,
        s4_discharge.TEMPLATE,
        s5_handover.TEMPLATE,
        s6_progress.TEMPLATE,
    )
}



_OWNED: set[tuple[str, str]] = set()


def _own_field(t, fkey: str):
    """common.py fields and options (CONSCIOUSNESS, VITALS_FIELD, PAIN_MED …) are the same objects in several templates, so
    a variant scoped to one record (("s5", "consciousness", "alert")) used to land in every record that shares it — the
    handover's "멘탈 alert, 오리엔테이션 있으십니다" showed up in the admission interview (2026-10-17). Copy before appending."""
    for sec in t.sections:
        for i, f in enumerate(sec.fields):
            if f.key == fkey:
                if (t.key, fkey) not in _OWNED:
                    sec.fields[i] = copy.deepcopy(f)
                    _OWNED.add((t.key, fkey))
                return sec.fields[i]
    return None


def _apply_extras() -> None:
    """Append the extra variant pack to the built-in option/field phrase lists (idempotent)."""
    for (tkey, fkey, slot), phrases in EXTRA.items():
        targets = TEMPLATES.values() if tkey == "*" else [TEMPLATES[tkey]] if tkey in TEMPLATES else []
        for t in targets:
            f = t.field_map().get(fkey) if tkey == "*" else _own_field(t, fkey)
            if f is None:
                continue
            if slot == "phrases":
                lst = f.phrases
            elif slot == "none":
                lst = f.none_phrases
            elif slot == "false":
                lst = f.false_phrases
            else:
                o = next((o for o in f.options if o.value == slot), None)
                if o is None:
                    continue
                lst = o.phrases
            for ph in phrases:
                if ph not in lst:
                    lst.append(ph)


_apply_extras()

for _t in TEMPLATES.values():
    if not any(sec.group == "protocol" for sec in _t.sections):
        extra = protocol_sections(_t.key)
        anchor = next((i for i, sec in enumerate(_t.sections) if sec.key == "d_morning"), None)   # S6: 정규 차팅 during the day shift
        if anchor is None:
            _t.sections.extend(extra)
        else:
            _t.sections[anchor + 1:anchor + 1] = extra

# Signal record kinds required by the recording spec.
RECORD_KINDS = ["간호정보조사", "퇴원간호", "수술전설명", "수술후설명", "인계", "경과기록"]


def get_template(key: str) -> RecordTemplate:
    try:
        return TEMPLATES[key]
    except KeyError:
        raise KeyError(f"unknown template: {key}") from None


def list_templates() -> list[dict]:
    return [t.to_schema() for t in TEMPLATES.values()]


def default_form(key: str) -> dict:
    t = get_template(key)
    form: dict = {}
    for _, f in t.iter_fields():
        if f.default is not None:
            form[f.key] = f.default
    return form
