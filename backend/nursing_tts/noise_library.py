"""User-uploaded noise clips (stored under data_dir()/noises)."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from .audio.io import duration, normalize_peak, read_audio, write_wav
from .audio.mixer import NoiseClip
from .config import data_dir


def _dir() -> Path:
    return data_dir() / "noises"


def _index_path() -> Path:
    return _dir() / "library.json"


def _load() -> list[dict[str, Any]]:
    p = _index_path()
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []


def _save(items: list[dict[str, Any]]) -> None:
    _index_path().write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def list_custom() -> list[dict[str, Any]]:
    return _load()


def custom_clips() -> list[NoiseClip]:
    out = []
    for it in _load():
        p = _dir() / it["file"]
        if p.exists():
            out.append(NoiseClip(id=it["id"], label=it["label"], path=p, category="custom",
                                 continuous=bool(it.get("continuous")), gain=float(it.get("gain", 0.5))))
    return out


def is_floor(label: str) -> bool:
    """The room-tone recording is the always-on floor under every recording, not a selectable noise."""
    return "룸톤" in label or "room tone" in label.lower()


def catalogue() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []   # synthetic noises are no longer offered: only the ward's real recordings (user, 2026-10-16)
    for it in _load():
        if is_floor(it["label"]):
            continue
        items.append({"key": it["id"], "label": it["label"], "builtin": False, "continuous": bool(it.get("continuous")),
                      "duration": it.get("duration", 0), "file": it["file"]})
    return items


def add_custom(src: Path, label: str, continuous: bool = False, gain: float = 0.5, sr: int = 24000) -> dict[str, Any]:
    audio, _ = read_audio(src, sr)
    audio = normalize_peak(audio, 0.9)
    nid = "custom_" + uuid.uuid4().hex[:8]
    fname = f"{nid}.wav"
    write_wav(_dir() / fname, audio, sr)
    item = {"id": nid, "label": label.strip() or src.stem, "file": fname, "continuous": continuous, "gain": gain,
            "duration": round(len(audio) / sr, 2), "created": time.time()}
    items = _load()
    items.append(item)
    _save(items)
    return item


def update_custom(nid: str, **fields: Any) -> dict[str, Any] | None:
    items = _load()
    for it in items:
        if it["id"] == nid:
            for k in ("label", "continuous", "gain"):
                if k in fields and fields[k] is not None:
                    it[k] = fields[k]
            _save(items)
            return it
    return None


def delete_custom(nid: str) -> bool:
    items = _load()
    keep = []
    found = False
    for it in items:
        if it["id"] == nid:
            found = True
            p = _dir() / it["file"]
            if p.exists():
                p.unlink()
        else:
            keep.append(it)
    _save(keep)
    return found


def custom_path(nid: str) -> Path | None:
    for it in _load():
        if it["id"] == nid:
            p = _dir() / it["file"]
            return p if p.exists() else None
    return None
