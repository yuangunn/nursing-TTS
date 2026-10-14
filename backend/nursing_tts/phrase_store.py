"""User-manageable phrase library.

Built-in phrase variants live in the template files.  Users can view, add,
edit, delete and reset them per element from the UI; edits are stored as
overrides in ``data_dir()/phrases.json`` and applied at generation time.

Key scheme (all strings):
    template  : "s1".."s5", or "_vitals" / "_global"
    field     : field key, or "intros" / "closings" (for templates),
                "bp" / "hr" / "rr" / "bt" / "spo2" / "lead" / "ending" (for _vitals)
    slot      : option value for select/multi options, or "phrases" / "none" / "false" for field-level lists

Additionally the *style expander* derives casual sentence endings from formal
ones ("~하였습니다." -> "~했고요," / "~했어요.") so every element has at least
three registers without writing each by hand.
"""
from __future__ import annotations

import json
import random
import re
import threading
from typing import Any

from .config import data_dir, load_settings

_LOCK = threading.Lock()
_CACHE: dict[str, Any] | None = None


def _path():
    return data_dir() / "phrases.json"


def _load() -> dict[str, Any]:
    global _CACHE
    if _CACHE is None:
        p = _path()
        try:
            _CACHE = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except Exception:  # noqa: BLE001
            _CACHE = {}
    return _CACHE


def _save(data: dict[str, Any]) -> None:
    global _CACHE
    _CACHE = data
    _path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_override(template: str, field: str, slot: str) -> list[str] | None:
    return _load().get(template, {}).get(field, {}).get(slot)


def set_override(template: str, field: str, slot: str, phrases: list[str]) -> None:
    with _LOCK:
        data = _load()
        cleaned = [p.strip() for p in phrases if p and p.strip()]
        data.setdefault(template, {}).setdefault(field, {})[slot] = cleaned
        _save(data)


def reset_override(template: str, field: str | None = None, slot: str | None = None) -> None:
    with _LOCK:
        data = _load()
        if template not in data:
            return
        if field is None:
            data.pop(template, None)
        elif slot is None:
            data[template].pop(field, None)
        else:
            data[template].get(field, {}).pop(slot, None)
        _save(data)


def all_overrides() -> dict[str, Any]:
    return json.loads(json.dumps(_load()))


def import_overrides(data: dict[str, Any], replace: bool = False) -> int:
    with _LOCK:
        cur = {} if replace else _load()
        n = 0
        for t, fields in (data or {}).items():
            for f, slots in (fields or {}).items():
                for slot, phrases in (slots or {}).items():
                    if isinstance(phrases, list):
                        cur.setdefault(t, {}).setdefault(f, {})[slot] = [str(p) for p in phrases]
                        n += 1
        _save(cur)
        return n


def effective(template: str, field: str, slot: str, builtin: list[str]) -> list[str]:
    ov = get_override(template, field, slot)
    return list(ov) if ov is not None else list(builtin)


# ---------------------------------------------------------------------------
# Style expander: formal -> connective / casual endings
# ---------------------------------------------------------------------------

# (regex on the sentence end, connective form, casual polite form)
_END_RULES: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"하였습니다\.$"), "했고요,", "했어요."),
    (re.compile(r"하셨습니다\.$"), "하셨고요,", "하셨어요."),
    (re.compile(r"되었습니다\.$"), "됐고요,", "됐어요."),
    (re.compile(r"였습니다\.$"), "였고요,", "였어요."),
    (re.compile(r"했습니다\.$"), "했고요,", "했어요."),
    (re.compile(r"셨습니다\.$"), "셨고요,", "셨어요."),
    (re.compile(r"있습니다\.$"), "있고요,", "있어요."),
    (re.compile(r"없습니다\.$"), "없고요,", "없어요."),
    (re.compile(r"됩니다\.$"), "되고요,", "돼요."),
    (re.compile(r"합니다\.$"), "하고요,", "해요."),
    (re.compile(r"십니다\.$"), "시고요,", "세요."),
    (re.compile(r"갑니다\.$"), "가고요,", "가요."),
    (re.compile(r"옵니다\.$"), "오고요,", "와요."),
    (re.compile(r"듭니다\.$"), "들고요,", "들어요."),
    (re.compile(r"입니다\.$"), "이고요,", "@예요"),  # 예요/이에요 by batchim
]


def _batchim(ch: str) -> bool:
    code = ord(ch)
    return 0xAC00 <= code <= 0xD7A3 and (code - 0xAC00) % 28 != 0


def expand_styles(phrase: str) -> list[str]:
    """Return [formal, connective, casual] variants of a formal phrase (deduplicated)."""
    p = phrase.strip()
    for rx, conn, casual in _END_RULES:
        m = rx.search(p)
        if not m:
            continue
        stem = p[: m.start()]
        if casual == "@예요":
            prev = stem.rstrip()[-1] if stem.rstrip() else ""
            # digits/latin: decide by Korean reading of last char (digits mostly end with batchim except 2,4,5,9)
            if prev.isdigit():
                b = prev in "013678"
            elif _batchim(prev):
                b = True
            elif "가" <= prev <= "힣":
                b = False
            else:
                b = False
            casual_form = stem + ("이에요." if b else "예요.")
        else:
            casual_form = stem + casual
        return [p, stem + conn, casual_form]
    return [p]


def stylize(text: str, rng: random.Random, style: str = "mixed", allow_connective: bool = True,
            expand: bool | None = None) -> str:
    """Apply the style expander to an already-formatted sentence."""
    if expand is None:
        expand = bool(load_settings().get("auto_style_expand", True))
    if not expand or not text:
        return text
    variants = expand_styles(text)
    if len(variants) == 1:
        return text
    formal, conn, casual = variants
    if style == "formal":
        options, weights = [formal, conn, casual], [9, 1, 0]
    elif style == "casual":
        options, weights = [formal, conn, casual], [2, 4, 4]
    else:
        options, weights = [formal, conn, casual], [5, 3, 2]
    if not allow_connective:
        weights[1] = 0
    if sum(weights) == 0:
        return formal
    return rng.choices(options, weights=weights)[0]


def pick(phrases: list[str], rng: random.Random, style: str = "mixed", expand: bool | None = None) -> str | None:
    """Choose a phrase and (optionally) a derived register.

    style: formal | casual | mixed.  ``expand`` defaults to the ``auto_style_expand`` setting.
    """
    if not phrases:
        return None
    if expand is None:
        expand = bool(load_settings().get("auto_style_expand", True))
    base = rng.choice(phrases)
    if not expand:
        return base
    variants = expand_styles(base)
    if len(variants) == 1:
        return base
    formal, conn, casual = variants
    if style == "formal":
        weights = [8, 1, 1]
    elif style == "casual":
        weights = [2, 4, 4]
    else:
        weights = [5, 3, 2]
    return rng.choices([formal, conn, casual], weights=weights)[0]
