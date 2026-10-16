"""Voice profiles: registered nurse voices with one or more reference clips."""
from __future__ import annotations

import json
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .audio.io import duration, normalize_peak, read_audio, write_wav
from .config import data_dir


@dataclass
class VoiceSample:
    id: str
    file: str              # relative to the voice folder
    transcript: str
    script_id: str = ""
    duration: float = 0.0
    created: float = 0.0


@dataclass
class Voice:
    id: str
    name: str
    note: str = ""
    sex: str = ""
    created: float = 0.0
    samples: list[VoiceSample] = field(default_factory=list)
    primary_sample: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def voices_dir() -> Path:
    return data_dir() / "voices"


def _voice_path(voice_id: str) -> Path:
    return voices_dir() / voice_id


def _load(voice_id: str) -> Voice | None:
    p = _voice_path(voice_id) / "voice.json"
    if not p.exists():
        return None
    raw = json.loads(p.read_text(encoding="utf-8"))
    raw["samples"] = [VoiceSample(**s) for s in raw.get("samples", [])]
    return Voice(**raw)


def _save(v: Voice) -> None:
    p = _voice_path(v.id)
    p.mkdir(parents=True, exist_ok=True)
    (p / "voice.json").write_text(json.dumps(v.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


DEMO_TEXT = "안녕하세요, 이 목소리의 샘플입니다. 환자분 활력징후 혈압 120에 80, 맥박 72, 체온 36.7도 측정되었습니다."


ASSET_DEMOS = Path(__file__).resolve().parent / "assets" / "voice_demos"   # shipped with the app (scripts/build_voice_demos.py)


def bundled_demo(voice_id: str) -> Path | None:
    """Demo clip shipped in the bundle for this voice id, if any (FLAC)."""
    p = ASSET_DEMOS / f"{voice_id}.flac"
    return p if p.exists() else None


def demo_path(voice_id: str) -> Path:
    """Synthesised demo clip (a fixed sentence) so the source recordings are never played back when
    choosing a voice (user, 2026-10-16). Removed whenever the samples change."""
    return _voice_path(voice_id) / "demo.wav"


def invalidate_demo(voice_id: str) -> None:
    demo_path(voice_id).unlink(missing_ok=True)


def list_voices() -> list[Voice]:
    out = []
    for d in sorted(voices_dir().iterdir()):
        if d.is_dir():
            v = _load(d.name)
            if v:
                out.append(v)
    return out


def get_voice(voice_id: str) -> Voice | None:
    return _load(voice_id)


def create_voice(name: str, note: str = "", sex: str = "") -> Voice:
    v = Voice(id=uuid.uuid4().hex[:10], name=name.strip() or "이름 없음", note=note, sex=sex, created=time.time())
    _save(v)
    return v


def update_voice(voice_id: str, **fields: Any) -> Voice:
    v = _load(voice_id)
    if not v:
        raise KeyError(voice_id)
    for k in ("name", "note", "sex", "primary_sample"):
        if k in fields and fields[k] is not None:
            setattr(v, k, fields[k])
    if fields.get("primary_sample"):
        invalidate_demo(voice_id)
    _save(v)
    return v


def delete_voice(voice_id: str) -> None:
    p = _voice_path(voice_id)
    if p.exists():
        shutil.rmtree(p)


def _trim_silence(audio: np.ndarray, sr: int, thresh: float = 0.01, pad: float = 0.15) -> np.ndarray:
    idx = np.where(np.abs(audio) > thresh)[0]
    if idx.size == 0:
        return audio
    a = max(0, idx[0] - int(pad * sr))
    b = min(len(audio), idx[-1] + int(pad * sr))
    return audio[a:b]


def add_sample(voice_id: str, src_path: Path, transcript: str, script_id: str = "",
               target_sr: int = 24000) -> VoiceSample:
    """Normalise a recorded/uploaded clip into the voice folder."""
    v = _load(voice_id)
    if not v:
        raise KeyError(voice_id)
    audio, sr = read_audio(src_path, target_sr)
    audio = _trim_silence(audio, sr)
    audio = normalize_peak(audio, 0.9)
    sid = uuid.uuid4().hex[:8]
    fname = f"{sid}.wav"
    write_wav(_voice_path(voice_id) / fname, audio, sr)
    s = VoiceSample(id=sid, file=fname, transcript=transcript.strip(), script_id=script_id,
                    duration=round(len(audio) / sr, 2), created=time.time())
    v.samples.append(s)
    if not v.primary_sample:
        v.primary_sample = sid
    invalidate_demo(voice_id)
    _save(v)
    return s


def add_sample_array(voice_id: str, audio: np.ndarray, sr: int, transcript: str, script_id: str = "") -> VoiceSample:
    v = _load(voice_id)
    if not v:
        raise KeyError(voice_id)
    audio = normalize_peak(_trim_silence(audio, sr), 0.9)
    sid = uuid.uuid4().hex[:8]
    fname = f"{sid}.wav"
    write_wav(_voice_path(voice_id) / fname, audio, sr)
    s = VoiceSample(id=sid, file=fname, transcript=transcript.strip(), script_id=script_id,
                    duration=round(len(audio) / sr, 2), created=time.time())
    v.samples.append(s)
    if not v.primary_sample:
        v.primary_sample = sid
    invalidate_demo(voice_id)
    _save(v)
    return s


def delete_sample(voice_id: str, sample_id: str) -> Voice:
    v = _load(voice_id)
    if not v:
        raise KeyError(voice_id)
    keep = []
    for s in v.samples:
        if s.id == sample_id:
            f = _voice_path(voice_id) / s.file
            if f.exists():
                f.unlink()
        else:
            keep.append(s)
    v.samples = keep
    if v.primary_sample == sample_id:
        v.primary_sample = keep[0].id if keep else ""
    invalidate_demo(voice_id)
    _save(v)
    return v


def sample_path(voice_id: str, sample_id: str) -> Path | None:
    v = _load(voice_id)
    if not v:
        return None
    s = next((s for s in v.samples if s.id == sample_id), None)
    return _voice_path(voice_id) / s.file if s else None


_QUESTION = ("까요", "세요?", "실까요", "을까요", "?")


def sample_style(transcript: str) -> str:
    """'interview' when the clip is a nurse asking the patient (간호정보조사 문진), else 'dictation'."""
    return "interview" if any(m in (transcript or "") for m in _QUESTION) else "dictation"


def pick_reference(voice_id: str, rng=None, prefer_primary: bool = False, style: str | None = None) -> tuple[Path, str] | None:
    """Choose a reference clip (path, transcript) for cloning.

    Rotating between samples gives extra variety across a batch; the primary sample is used when
    ``prefer_primary`` is set.  ``style`` ('interview' for admission interviews, 'dictation' for the
    rest) prefers clips in the same register, because the clone copies the reference's intonation:
    a question-style clip makes a handover sound like questions.  Falls back to all clips.
    """
    v = _load(voice_id)
    if not v or not v.samples:
        return None
    if prefer_primary or rng is None:
        s = next((s for s in v.samples if s.id == v.primary_sample), v.samples[0])
    else:
        pool = [s for s in v.samples if style is None or sample_style(s.transcript) == style] or v.samples
        good_len = [s for s in pool if 6.0 <= float(getattr(s, "duration", 0) or 0) <= 13.0] or pool
        s = rng.choice(good_len)
    return _voice_path(voice_id) / s.file, s.transcript
