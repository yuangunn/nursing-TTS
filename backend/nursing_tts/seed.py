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
SEED_VERSION = 1


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
    if int(done.get("version") or 0) >= SEED_VERSION:
        return {"voices": 0, "noises": 0}
    seed = seed_contents()
    added = {"voices": 0, "noises": 0}
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
