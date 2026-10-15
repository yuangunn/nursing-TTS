"""Persistent app settings and data directories."""
from __future__ import annotations

import json
import os
import platform
import threading
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()


def data_dir() -> Path:
    env = os.environ.get("NURSING_TTS_DATA")
    if env:
        p = Path(env)
    elif platform.system() == "Windows":
        p = Path(os.environ.get("APPDATA", Path.home())) / "NursingTTS"
    elif platform.system() == "Darwin":
        p = Path.home() / "Library" / "Application Support" / "NursingTTS"
    else:
        p = Path.home() / ".nursing-tts"
    p.mkdir(parents=True, exist_ok=True)
    for sub in ("voices", "noises", "output", "cache"):
        (p / sub).mkdir(exist_ok=True)
    return p


DEFAULTS: dict[str, Any] = {
    "tts_engine": "auto",          # auto | qwen | http | system | silent
    "device": "auto",              # auto | cuda | mps | cpu
    "qwen_model": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",  # built-in cloning model (HF id or local path)
    "qwen_idle_unload_min": 10,    # drop the model from memory after this many idle minutes (0 = keep)
    "qwen_batch": 8,               # sentence chunks per generate call (1 = one at a time)
    "http_tts_url": "http://127.0.0.1:8081/synthesize",
    "output_dir": "",              # empty -> data_dir()/output
    "sample_rate": 24000,
    "output_format": "wav",        # wav only for now
    "llm_provider": "none",        # none | anthropic | openai_compatible
    "llm_api_key": "",
    "llm_model": "",
    "llm_base_url": "",
    "default_style": "mixed",      # formal | casual | mixed
    "noise_default_level": 35,     # 0..100
    "floor_dbfs": -56.0,           # faint room-tone bed under every recording, even with noise off (0 = none)
    "room_wet": 0.06,              # very light room reverb on every recording (0 = none)
    "asr_verify": False,           # transcribe each clip with faster-whisper and flag high CER
    "asr_model": "small",          # tiny | base | small | medium | large-v3
    "asr_device": "auto",
    "cer_threshold": 0.25,
    "chunk_cer_threshold": 0.3,    # per-sentence read-back CER above this -> re-synthesize that sentence
    "chunk_retries": 2,            # how many new takes to try per bad sentence (0 = off)
    "loudness_dbfs": -20.0,        # RMS loudness target for the speech layer
    "default_disfluency": 0,       # 0..3
    "auto_style_expand": True,     # derive ~고요,/~어요. from formal phrases
    "signal_format": "strict",     # strict | <format key> | random
    "signal_aliases": False,       # allow kind aliases (간호정보조사지, 퇴원 교육 ...) in the signal
    # rounds-dialogue noise: per-role pitch shift (semitones) and tempo (1.0 = the registered voice's own pace)
    "rounds_shift": {"doctor": -4.0, "patient": -1.0, "nurse": 3.0},
    "rounds_tempo": {"doctor": 1.05, "patient": 0.9, "nurse": 1.15},
    "rounds_tempo_jitter": 0.08,   # +-random tempo per line so speakers don't sound metronomic
}


def _settings_path() -> Path:
    return data_dir() / "settings.json"


def load_settings() -> dict[str, Any]:
    with _LOCK:
        p = _settings_path()
        data = dict(DEFAULTS)
        if p.exists():
            try:
                data.update(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                pass
        return data


def save_settings(update: dict[str, Any]) -> dict[str, Any]:
    with _LOCK:
        p = _settings_path()
        data = dict(DEFAULTS)
        if p.exists():
            try:
                data.update(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                pass
        for k, v in update.items():
            if k in DEFAULTS:
                data[k] = v
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data


def output_dir() -> Path:
    s = load_settings()
    p = Path(s["output_dir"]) if s.get("output_dir") else data_dir() / "output"
    p.mkdir(parents=True, exist_ok=True)
    return p
