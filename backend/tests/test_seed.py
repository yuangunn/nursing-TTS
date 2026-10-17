"""Shipped seed data (public voices + ward noises) lands in a fresh data folder once, and deletions stick."""
import json
import shutil

from nursing_tts.seed import SEED_DIR, SEED_VERSION, ensure_seed_data, seed_contents


def test_seed_copies_public_voices_and_noises_once(tmp_path):
    seed = seed_contents()
    assert len(seed["voices"]) >= 10 and len(seed["noises"]) >= 4
    assert "481e0ff97c" not in seed["voices"]            # the nurse's private recordings never ship
    for vid in seed["voices"]:
        meta = json.loads((SEED_DIR / "voices" / vid / "voice.json").read_text(encoding="utf-8"))
        assert "Zeroth" in meta.get("note", "") and meta["samples"] and not (SEED_DIR / "voices" / vid / "demo.wav").exists()
        for smp in meta["samples"]:
            assert (SEED_DIR / "voices" / vid / smp["file"]).exists()
    added = ensure_seed_data(tmp_path)
    assert added == {"voices": len(seed["voices"]), "noises": len(seed["noises"]), "removed": 0}
    lib = json.loads((tmp_path / "noises" / "library.json").read_text(encoding="utf-8"))
    assert [n["id"] for n in lib] == seed["noises"] and all((tmp_path / "noises" / n["file"]).exists() for n in lib)
    assert json.loads((tmp_path / "seed.json").read_text())["version"] == SEED_VERSION
    # the user deletes a voice and a clip: the next start must not bring them back
    shutil.rmtree(tmp_path / "voices" / seed["voices"][0])
    lib = lib[1:]
    (tmp_path / "noises" / "library.json").write_text(json.dumps(lib), encoding="utf-8")
    assert ensure_seed_data(tmp_path) == {"voices": 0, "noises": 0, "removed": 0}
    assert not (tmp_path / "voices" / seed["voices"][0]).exists()
    assert len(json.loads((tmp_path / "noises" / "library.json").read_text())) == len(seed["noises"]) - 1


def test_seeded_voices_and_noises_are_usable(tmp_path, monkeypatch):
    monkeypatch.setenv("NURSING_TTS_DATA", str(tmp_path))
    from nursing_tts import noise_library, voices
    ensure_seed_data(tmp_path)
    names = [v.name for v in voices.list_voices()]
    assert any(n.startswith("기본 음성 여") for n in names) and any(n.startswith("기본 음성 남") for n in names)
    assert all(voices.pick_reference(v.id) is not None for v in voices.list_voices())
    clips = noise_library.custom_clips()
    labels = " ".join(c.label for c in clips)
    assert len(clips) >= 4 and "네뷸라이저" in labels and "알람" in labels and "회진" in labels
    assert any(noise_library.is_floor(c.label) for c in clips)        # the room tone floor comes with it


def test_seed_upgrade_retires_the_old_clips(tmp_path, monkeypatch):
    """Seed v2 (user 2026-10-17): the online-video noise clips are replaced by the ward's own recordings; an install that
    already has the v1 clips loses them and gains the new ones, while its own clips and the untouched seed clips stay."""
    import json
    from nursing_tts import seed as seed_mod
    data = tmp_path / "d"; (data / "noises").mkdir(parents=True)
    old = [{"id": "custom_7d436e34", "label": "네뷸라이저 작동음 (실제 녹음)", "file": "custom_7d436e34.wav", "continuous": True, "gain": 0.5, "duration": 60.0, "created": 1.0},
           {"id": "custom_mine0001", "label": "내 병동 소음", "file": "custom_mine0001.wav", "continuous": True, "gain": 0.5, "duration": 3.0, "created": 2.0}]
    for it in old:
        (data / "noises" / it["file"]).write_bytes(b"RIFF")
    (data / "noises" / "library.json").write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
    (data / "seed.json").write_text(json.dumps({"version": 1, "voices": [], "noises": ["custom_7d436e34"]}), encoding="utf-8")
    added = seed_mod.ensure_seed_data(data)
    lib = {it["id"]: it for it in json.loads((data / "noises" / "library.json").read_text(encoding="utf-8"))}
    assert added["removed"] == 1 and "custom_7d436e34" not in lib and not (data / "noises" / "custom_7d436e34.wav").exists()
    assert "custom_mine0001" in lib and (data / "noises" / "custom_mine0001.wav").exists()
    labels = " ".join(it["label"] for it in lib.values())
    assert "네뷸라이저" in labels and "모니터 알람" in labels and "주입 펌프" in labels and "산소 5L" in labels and "병동 녹음" in labels
    assert json.loads((data / "seed.json").read_text())["version"] == seed_mod.SEED_VERSION
    assert seed_mod.ensure_seed_data(data) == {"voices": 0, "noises": 0, "removed": 0}
