"""Pick a TTS engine from settings."""
from __future__ import annotations

from typing import Any

from .f5 import F5Engine
from .http_engine import HttpTTSEngine
from .silent import SilentEngine
from .system import SystemTTSEngine

_CACHE: dict[str, Any] = {}


def build_engines(settings: dict[str, Any]) -> dict[str, Any]:
    sr = int(settings.get("sample_rate", 24000))
    sig = (settings.get("f5_model"), settings.get("f5_ckpt_file"), settings.get("f5_vocab_file"),
           settings.get("device"), settings.get("f5_nfe_step"), settings.get("f5_speed"), sr,
           settings.get("http_tts_url"))
    if _CACHE.get("sig") != sig:
        _CACHE.clear()
        _CACHE["sig"] = sig
        _CACHE["engines"] = {
            "f5": F5Engine(model=settings.get("f5_model") or "F5TTS_v1_Base",
                           ckpt_file=settings.get("f5_ckpt_file") or "",
                           vocab_file=settings.get("f5_vocab_file") or "",
                           device=settings.get("device") or "auto",
                           nfe_step=settings.get("f5_nfe_step") or 32,
                           speed=settings.get("f5_speed") or 1.0, sr=sr),
            "http": HttpTTSEngine(settings.get("http_tts_url") or "", sr=sr),
            "system": SystemTTSEngine(sr=sr),
            "silent": SilentEngine(sr=sr),
        }
    return _CACHE["engines"]


def engine_status(settings: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for key, eng in build_engines(settings).items():
        ok, msg = eng.available()
        out.append({"key": key, "label": eng.label, "available": ok, "status": msg, "clones_voice": eng.clones_voice})
    return out


def get_engine(settings: dict[str, Any]):
    engines = build_engines(settings)
    pref = settings.get("tts_engine", "auto")
    if pref != "auto":
        return engines[pref]
    for key in ("f5", "http", "system", "silent"):
        ok, _ = engines[key].available()
        if ok:
            return engines[key]
    return engines["silent"]
