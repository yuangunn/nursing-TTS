"""Pick a TTS engine from settings."""
from __future__ import annotations

from typing import Any

from .http_engine import HttpTTSEngine
from .qwen import QwenEngine
from .silent import SilentEngine
from .system import SystemTTSEngine

_CACHE: dict[str, Any] = {}


def build_engines(settings: dict[str, Any]) -> dict[str, Any]:
    sr = int(settings.get("sample_rate", 24000))
    sig = (settings.get("qwen_model"), settings.get("device"), settings.get("qwen_idle_unload_min"), sr,
           settings.get("http_tts_url"), settings.get("qwen_batch"))
    if _CACHE.get("sig") != sig:
        _CACHE.clear()
        _CACHE["sig"] = sig
        _CACHE["engines"] = {
            "qwen": QwenEngine(model=settings.get("qwen_model") or "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
                               device=settings.get("device") or "auto", sr=sr,
                               idle_unload_min=settings.get("qwen_idle_unload_min", 10),
                               batch=settings.get("qwen_batch", 8)),
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
    if pref in engines:
        return engines[pref]
    for key in ("qwen", "http", "system", "silent"):  # unknown pref (e.g. "f5" from an older settings file) -> auto
        ok, _ = engines[key].available()
        if ok:
            return engines[key]
    return engines["silent"]
