"""Declarative record templates.

A template is a list of sections; each section a list of fields.  Every option
or value carries several *spoken* phrase variants.  Variants that end with a
comma are "connective" (…하시구요,) and will be glued to the next fragment;
variants ending with a period close a sentence.  The generator picks one
variant per field at random so that the same form data yields many different
narrations.

Placeholders available in every phrase:
  {v}        the field value (number/text) or the joined list (multi)
  {unit}     the field unit
  {name} {age} {sex} {dx} {surgery} {surgery_ko} {prof} {dept} {pod}
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Option:
    value: str
    label: str
    phrases: list[str] = field(default_factory=list)
    # Short noun forms used when this option is part of a multi-select list
    nouns: list[str] = field(default_factory=list)

    def to_schema(self) -> dict[str, Any]:
        return {"value": self.value, "label": self.label}


@dataclass
class Field:
    key: str
    label: str
    kind: str = "select"  # select | multi | number | text | bool | vitals | date | time
    options: list[Option] = field(default_factory=list)
    phrases: list[str] = field(default_factory=list)      # number/text/bool(true)/multi
    false_phrases: list[str] = field(default_factory=list)  # bool(false)
    none_phrases: list[str] = field(default_factory=list)   # multi with nothing selected
    unit: str = ""
    default: Any = None
    min: float | None = None
    max: float | None = None
    step: float | None = None
    hint: str = ""        # 들어가면 좋은 내용
    example: str = ""     # 예시 발화
    placeholder: str = ""
    # Probability (0..1) that an *optional* filled value is actually spoken.
    speak_prob: float = 1.0
    # Values of this field that mean "skip" (e.g. "none").
    skip_values: tuple[str, ...] = ()
    # Random generator hint for virtual patients: list of candidate values,
    # or a (min,max) range for numbers. None -> pick from options / defaults.
    random: Any = None

    def to_schema(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "kind": self.kind,
            "options": [o.to_schema() for o in self.options],
            "unit": self.unit,
            "default": self.default,
            "min": self.min,
            "max": self.max,
            "step": self.step,
            "hint": self.hint,
            "example": self.example,
            "placeholder": self.placeholder,
        }


@dataclass
class Section:
    key: str
    title: str
    fields: list[Field]
    hint: str = ""
    group: str = ""   # "" = template's own content, "protocol" = nursing protocol checklist

    def to_schema(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "hint": self.hint,
            "group": self.group,
            "fields": [f.to_schema() for f in self.fields],
        }


@dataclass
class RecordTemplate:
    key: str
    title: str
    signal_kind: str
    description: str
    sections: list[Section]
    closings: list[str]
    # Optional spoken intro right after the signal line (e.g. diagnosis recap)
    intros: list[str] = field(default_factory=list)

    def to_schema(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "signal_kind": self.signal_kind,
            "description": self.description,
            "sections": [s.to_schema() for s in self.sections],
        }

    def iter_fields(self):
        for s in self.sections:
            for f in s.fields:
                yield s, f

    def field_map(self) -> dict[str, Field]:
        return {f.key: f for _, f in self.iter_fields()}


# ---------------------------------------------------------------------------
# Small helpers used by the template files
# ---------------------------------------------------------------------------

def opt(value: str, label: str | None = None, *phrases: str, nouns: list[str] | None = None) -> Option:
    return Option(value=value, label=label or value, phrases=list(phrases), nouns=nouns or [label or value])


def none_opt(*phrases: str) -> Option:
    return Option(value="none", label="해당 없음/특이사항 없음", phrases=list(phrases), nouns=[])


def sel(key: str, label: str, options: list[Option], **kw) -> Field:
    return Field(key=key, label=label, kind="select", options=options, **kw)


def multi(key: str, label: str, options: list[Option], phrases: list[str], none_phrases: list[str] | None = None, **kw) -> Field:
    return Field(key=key, label=label, kind="multi", options=options, phrases=phrases,
                 none_phrases=none_phrases or [], **kw)


def num(key: str, label: str, phrases: list[str], unit: str = "", **kw) -> Field:
    return Field(key=key, label=label, kind="number", phrases=phrases, unit=unit, **kw)


def txt(key: str, label: str, phrases: list[str], **kw) -> Field:
    return Field(key=key, label=label, kind="text", phrases=phrases, **kw)


def boolean(key: str, label: str, phrases: list[str], false_phrases: list[str] | None = None, **kw) -> Field:
    return Field(key=key, label=label, kind="bool", phrases=phrases, false_phrases=false_phrases or [], **kw)
