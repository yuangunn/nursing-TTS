"""Seed data shipped inside the installer (user 2026-10-17: "설치 파일만 실행하면 기본 목소리와 소음도 깔리게").

``assets/seed/voices/<id>/`` holds the public Zeroth-Korean voices (CC BY 4.0, see ATTRIBUTION.md) and
``assets/seed/noises/`` the ward noise clips with their library entries.  On the first start with a given data
folder they are copied in; a version marker (``seed.json``) keeps later starts from re-adding voices or clips the
user deleted.  Private recordings (the nurse's own voice) are never part of the seed — they travel in a user-made
offline bundle (``build-offline-bundle --data``) only.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

SEED_DIR = Path(__file__).resolve().parent / "assets" / "seed"
SEED_VERSION = 2
# seed ids retired in a later version (2: the online-video clips were replaced by the ward's own recordings, user 2026-10-17);
# an upgrade removes them from the data folder so the old clips do not linger next to the new ones
SEED_REMOVED: dict[int, set[str]] = {2: {"custom_7d436e34", "custom_d046b2d9", "custom_b75bb01b"}}


def seed_contents() -> dict[str, Any]:
    voices = sorted(p.name for p in (SEED_DIR / "voices").glob("*") if (p / "voice.json").exists()) if (SEED_DIR / "voices").exists() else []
    noises: list[dict[str, Any]] = []
    lib = SEED_DIR / "noises" / "library.json"
    if lib.exists():
        try:
            noises = json.loads(lib.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            noises = []
    return {"version": SEED_VERSION, "voices": voices, "noises": [n["id"] for n in noises], "noise_entries": noises}


def ensure_seed_data(data_dir: Path) -> dict[str, int]:
    """Copy seed voices and noise clips the data folder does not have yet. Runs once per seed version."""
    marker = data_dir / "seed.json"
    done: dict[str, Any] = {}
    if marker.exists():
        try:
            done = json.loads(marker.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            done = {}
    have_version = int(done.get("version") or 0)
    if have_version >= SEED_VERSION:
        return {"voices": 0, "noises": 0, "removed": 0}
    seed = seed_contents()
    added = {"voices": 0, "noises": 0, "removed": 0}
    retired = set().union(*(ids for v, ids in SEED_REMOVED.items() if have_version < v <= SEED_VERSION)) if SEED_REMOVED else set()
    vdir = data_dir / "voices"
    vdir.mkdir(parents=True, exist_ok=True)
    for vid in seed["voices"]:
        if (vdir / vid).exists():
            continue
        shutil.copytree(SEED_DIR / "voices" / vid, vdir / vid)
        added["voices"] += 1
    ndir = data_dir / "noises"
    ndir.mkdir(parents=True, exist_ok=True)
    lib_path = ndir / "library.json"
    try:
        items = json.loads(lib_path.read_text(encoding="utf-8")) if lib_path.exists() else []
    except Exception:  # noqa: BLE001
        items = []
    if retired:
        keep = []
        for it in items:
            if it.get("id") in retired:
                (ndir / str(it.get("file") or "")).unlink(missing_ok=True)
                added["removed"] += 1
            else:
                keep.append(it)
        if len(keep) != len(items):
            items = keep
            lib_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    have = {it.get("id") for it in items}
    for entry in seed["noise_entries"]:
        if entry["id"] in have:
            continue
        src = SEED_DIR / "noises" / entry["file"]
        if not src.exists():
            continue
        shutil.copy2(src, ndir / entry["file"])
        items.append(entry)
        added["noises"] += 1
    if added["noises"]:
        lib_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    marker.write_text(json.dumps({"version": SEED_VERSION, "voices": seed["voices"], "noises": seed["noises"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    return added
