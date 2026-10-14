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
    "tts_engine": "auto",          # auto | f5 | http | system | silent
    "device": "auto",              # auto | cuda | mps | cpu
    "f5_model": "F5TTS_v1_Base",
    "f5_ckpt_file": "",            # Korean fine-tuned checkpoint (.pt/.safetensors)
    "f5_vocab_file": "",
    "f5_nfe_step": 32,
    "f5_speed": 1.0,
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
    "asr_verify": False,           # transcribe each clip with faster-whisper and flag high CER
    "asr_model": "small",          # tiny | base | small | medium | large-v3
    "asr_device": "auto",
    "cer_threshold": 0.25,
    "loudness_dbfs": -20.0,        # RMS loudness target for the speech layer
    "default_disfluency": 0,       # 0..3
    "auto_style_expand": True,     # derive ~고요,/~어요. from formal phrases
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
