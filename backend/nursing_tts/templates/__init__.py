"""Record template registry."""
from __future__ import annotations

from .base import RecordTemplate
from . import s1_admission, s2_preop, s3_postop, s3_2_event, s4_discharge, s5_handover

TEMPLATES: dict[str, RecordTemplate] = {
    t.key: t for t in (
        s1_admission.TEMPLATE,
        s2_preop.TEMPLATE,
        s3_postop.TEMPLATE,
        s3_2_event.TEMPLATE,
        s4_discharge.TEMPLATE,
        s5_handover.TEMPLATE,
    )
}

# Signal record kinds required by the recording spec.
RECORD_KINDS = ["간호정보조사", "퇴원간호", "수술전설명", "수술후설명", "인계"]


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
