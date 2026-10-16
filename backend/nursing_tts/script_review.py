"""Script review notes: sentences a nurse flagged as "이렇게 말 안 한다" while reading generated scripts.

Stored as a json list in the data folder; the list is exported as markdown so the phrase pools / BAD
patterns can be fixed from it.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

from .config import data_dir


def _path():
    return data_dir() / "script_review.json"


def load() -> list[dict[str, Any]]:
    p = _path()
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []


def _save(items: list[dict[str, Any]]) -> None:
    _path().parent.mkdir(parents=True, exist_ok=True)
    _path().write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def add(flag: dict[str, Any]) -> dict[str, Any]:
    items = load()
    item = {"id": uuid.uuid4().hex[:8], "created": time.time(),
            "template": flag.get("template", ""), "record_kind": flag.get("record_kind", ""),
            "patient": flag.get("patient", ""), "style": flag.get("style", ""), "seed": flag.get("seed"),
            "sentence": (flag.get("sentence") or "").strip(), "note": (flag.get("note") or "").strip()}
    items.append(item)
    _save(items)
    return item


def update(flag_id: str, note: str) -> dict[str, Any] | None:
    items = load()
    for it in items:
        if it["id"] == flag_id:
            it["note"] = note.strip()
            _save(items)
            return it
    return None


def remove(flag_id: str | None) -> int:
    items = load()
    keep = [] if flag_id is None else [it for it in items if it["id"] != flag_id]
    _save(keep)
    return len(items) - len(keep)


def as_markdown(items: list[dict[str, Any]] | None = None) -> str:
    items = load() if items is None else items
    lines = ["# 대본 검토: 이렇게 말 안 한다", ""]
    for it in items:
        note = f" — {it['note']}" if it.get("note") else ""
        lines.append(f"- [{it.get('record_kind') or it.get('template')}] {it['sentence']}{note}")
    return "\n".join(lines) + "\n"
