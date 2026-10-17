"""Background generation jobs (single recording or bulk)."""
from __future__ import annotations

import json
import random
import re
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from . import disfluency, llm, verify as verify_mod, voices as voices_mod
from .audio.augment import AugmentConfig, augment
from .rounds import pitch_shift, time_stretch
from .audio.io import normalize_peak, resample, rms, write_wav
from .audio.mixer import NoiseClip, NoiseConfig, mix
from .config import load_settings, output_dir
from .fake import random_form, random_patient, record_datetime
from .generator import Patient, build_script
from .templates import get_template
from .tts.base import natural_pause, synthesize_script
from .tts.registry import get_engine


def _patient_voice(spec: dict[str, Any], patient: Patient, voice_id: str, rng: random.Random):
    """Who speaks the patient's lines: an explicit registered voice, "auto" = a registered voice of the patient's sex
    (the public 기본 음성 ones qualify), or the nurse's own voice shifted down (men −5, women −2 semitones; 80+ slower)."""
    choice = spec.get("patient_voice_id") or "auto"
    male = patient.sex.startswith("남")
    old = (patient.age or 0) >= 80
    v = voices_mod.get_voice(choice) if choice not in ("auto", "same") else None
    if v is None and choice == "auto":
        cands = [c for c in voices_mod.list_voices() if c.id != voice_id and c.samples and c.sex and c.sex[0] == patient.sex[:1]]
        v = rng.choice(cands) if cands else None
    if v is not None and v.samples:                        # the voice's own preset applies, 80+ a little slower
        return voices_mod.pick_reference(v.id, rng=rng), (float(v.pitch or 0.0), float(v.tempo or 1.0) * (0.88 if old else 1.0)), v.name
    shift = (-5.0 if male else -2.0) - (1.0 if old else 0.0)
    return None, (shift, 0.85 if old else 0.95), ""


def _synthesize_turns(engine, spoken_lines: list[str], tts_lines: list[str], speakers: list[str], refs: dict[str, Any],
                      shift: dict[str, tuple[float, float]], seed: int, rng: random.Random, progress=None, **kw):
    """Runs of consecutive same-speaker lines are synthesized with that speaker's reference voice and joined with a
    short turn gap; segments carry the speaker."""
    runs: list[tuple[str, list[int]]] = []
    for i, sp in enumerate(speakers):
        if runs and runs[-1][0] == sp:
            runs[-1][1].append(i)
        else:
            runs.append((sp, [i]))
    pieces: list[np.ndarray] = []
    segments: list[dict] = []
    pos, sr = 0, 24000
    for r, (sp, idxs) in enumerate(runs):
        a, sr, segs = synthesize_script(engine, [spoken_lines[i] for i in idxs], [tts_lines[i] for i in idxs], refs.get(sp),
                                        seed + 101 * r, progress=None, **kw)
        ps, pt = shift.get(sp, (0.0, 1.0))
        if ps:
            a = pitch_shift(a, sr, ps)
        if pt != 1.0:
            a = time_stretch(a, pt)
            segs = [{**s, "start": s["start"] / pt, "end": s["end"] / pt} for s in segs]
        if r > 0:
            gap = int(natural_pause(rng, 0.9) * sr)
            pieces.append(np.zeros(gap, dtype=np.float32))
            pos += gap
        pieces.append(a)
        segments += [{**s, "start": round(s["start"] + pos / sr, 3), "end": round(s["end"] + pos / sr, 3), "speaker": sp} for s in segs]
        pos += len(a)
        if progress:
            progress(idxs[-1] + 1, len(speakers))
    return np.concatenate(pieces) if pieces else np.zeros(sr // 2, dtype=np.float32), sr, segments

ROUNDS_LINES = [
    "네, 어제보다 많이 좋아지셨네요. 오늘 가스 나오면 물부터 드셔 보시고요, 내일 아침에 한 번 더 볼게요.",
    "통증은 어떠세요? 많이 걸으셔야 해요. 하루에 복도 다섯 바퀴 이상 걸으시고요.",
    "검사 결과는 괜찮습니다. 드레싱은 내일 소독하고 실밥은 외래에서 뽑겠습니다.",
    "식사 잘 드세요? 네, 그러면 내일 죽으로 올리겠습니다. 뭐 불편한 거 있으세요?",
    "열이 좀 있으셨죠. 심호흡 열심히 하시고 폐활량계 자주 하셔야 해요.",
]


@dataclass
class JobItem:
    index: int
    status: str = "pending"      # pending | running | done | error
    patient: str = ""
    template: str = ""
    files: dict[str, str] = field(default_factory=dict)
    duration: float = 0.0
    error: str = ""
    spoken_text: str = ""
    verify: dict[str, Any] | None = None


@dataclass
class Job:
    id: str
    kind: str                     # single | batch
    total: int
    created: float = field(default_factory=time.time)
    status: str = "queued"        # queued | running | done | error | cancelled
    items: list[JobItem] = field(default_factory=list)
    message: str = ""
    error: str = ""
    cancel: bool = False
    folder: str = ""

    def to_dict(self) -> dict[str, Any]:
        done = sum(1 for i in self.items if i.status == "done")
        return {
            "id": self.id, "kind": self.kind, "total": self.total, "done": done, "status": self.status,
            "message": self.message, "error": self.error, "created": self.created, "folder": self.folder,
            "items": [i.__dict__ for i in self.items],
        }


_JOBS: dict[str, Job] = {}
_LOCK = threading.Lock()


def list_jobs() -> list[dict[str, Any]]:
    with _LOCK:
        return [j.to_dict() for j in sorted(_JOBS.values(), key=lambda j: j.created, reverse=True)[:50]]


def get_job(job_id: str) -> Job | None:
    return _JOBS.get(job_id)


def cancel_job(job_id: str) -> bool:
    j = _JOBS.get(job_id)
    if not j:
        return False
    j.cancel = True
    return True


# ---------------------------------------------------------------------------

def safe_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\s]+', "_", name.strip())
    return name or "patient"


def make_basename(when: datetime, patient_name: str, folder: Path) -> str:
    base = f"{when.strftime('%Y%m%d_%H%M')}_{safe_filename(patient_name)}"
    candidate = base
    k = 2
    while (folder / f"{candidate}.wav").exists():
        candidate = f"{base}_{k}"
        k += 1
    return candidate


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now().replace(second=0, microsecond=0)
    return datetime.fromisoformat(value)


def _noise_cfg(raw: dict[str, Any] | None, settings: dict[str, Any], rng: random.Random) -> NoiseConfig:
    raw = raw or {}
    return NoiseConfig(
        enabled=bool(raw.get("enabled", False)),
        level=int(raw.get("level", settings.get("noise_default_level", 35))),
        types=list(raw.get("types") or []),             # empty = all of the ward's real clips, each with each_prob
        each_prob=float(raw.get("each_prob", 0.6)),
        density=float(raw.get("density", 4.0)),
        reverb=bool(raw.get("reverb", False)),
        seed=rng.randrange(1 << 30),
        floor_dbfs=float(settings.get("floor_dbfs", -56.0) or 0),
        room_wet=float(settings.get("room_wet", 0.06) or 0),
    )


def _augment_cfg(raw: dict[str, Any] | None) -> AugmentConfig:
    raw = raw or {}
    return AugmentConfig(
        enabled=bool(raw.get("enabled", False)),
        channels=list(raw.get("channels") or ["studio", "smartphone", "lapel", "recorder"]),
        speed_min=float(raw.get("speed_min", 0.92)), speed_max=float(raw.get("speed_max", 1.08)),
        speed_prob=float(raw.get("speed_prob", 0.6)), gain_db_range=float(raw.get("gain_db_range", 6.0)),
        clip_prob=float(raw.get("clip_prob", 0.1)),
    )


def _loudness(audio: np.ndarray, target_dbfs: float) -> np.ndarray:
    r = rms(audio)
    if r < 1e-6:
        return audio
    gain = (10 ** (target_dbfs / 20)) / r
    out = audio * gain
    peak = float(np.max(np.abs(out)))
    if peak > 0.98:
        out = out / peak * 0.98
    return out.astype(np.float32)


def generate_one(spec: dict[str, Any], settings: dict[str, Any], custom_noises: list[NoiseClip],
                 item: JobItem | None = None, progress=None) -> dict[str, Any]:
    """spec keys: template, form, patient, datetime, style, seed, voice_id, noise, llm_polish, rounds_voice."""
    t_start = time.perf_counter()
    rng = random.Random(spec.get("seed"))
    seed = spec.get("seed") if spec.get("seed") is not None else rng.randrange(1 << 30)
    template_key = spec["template"]
    patient = Patient(**{k: v for k, v in (spec.get("patient") or {}).items() if k in Patient.__dataclass_fields__})
    when = _parse_dt(spec.get("datetime"))
    style = spec.get("style") or settings.get("default_style", "formal")
    sig_fmt = spec.get("signal_format") or settings.get("signal_format", "strict")
    dialogue = bool(spec.get("dialogue")) and template_key == "s1"
    script = build_script(template_key, spec.get("form") or {}, patient, when, style=style, seed=seed,
                          signal_format=sig_fmt, signal_aliases=bool(spec.get("signal_aliases", settings.get("signal_aliases", False))),
                          dialogue=dialogue)
    speakers = [t["speaker"] for t in script.turns] if dialogue else []

    spoken = script.spoken_text
    polished = False
    override = (spec.get("text_override") or "").strip()
    if override:
        from .korean import to_tts_text
        from .dialogue import strip_prefix
        raw_lines = [l for l in override.splitlines() if l.strip()]
        parsed = [strip_prefix(l) for l in raw_lines]            # "환자: …" lines keep their speaker through hand edits
        lines = [t for _, t in parsed]
        speakers = [sp for sp, _ in parsed] if dialogue else []
        script.turns = [{"speaker": sp, "text": t} for sp, t in parsed] if dialogue else []
        script.spoken_text = "\n".join(lines)
        script.signal = lines[0] if lines else script.signal
        sig_tts = script.tts_text.splitlines()[0] if lines and lines[0] == script.sentences[0] else to_tts_text(lines[0], random.Random(seed + 5))
        script.tts_text = "\n".join([sig_tts] + [to_tts_text(l, random.Random(seed + 7 + i)) for i, l in enumerate(lines[1:])])
        script.sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", script.spoken_text) if x.strip()]
        spoken = script.spoken_text
        from .signal import parse as _parse_sig
        _ps = _parse_sig(lines[0] if lines else "")
        script.structured["signal_format"] = _ps.format if _ps.ok else "custom"
        if not _ps.ok:
            script.structured["signal_warning"] = f"시그널 인식 실패 (누락: {', '.join(_ps.missing or [])})"
    elif spec.get("llm_polish") and not dialogue:   # the LLM would merge the two speakers' lines
        new = llm.polish(spoken, settings)
        if new != spoken:
            spoken = new
            polished = True
            from .korean import to_tts_text
            lines = spoken.splitlines()
            tts_lines = [script.tts_text.splitlines()[0]] + [to_tts_text(l, random.Random(seed + 7)) for l in lines[1:]]
            script.tts_text = "\n".join(tts_lines)
            script.spoken_text = spoken

    # --- spoken disfluencies (fillers / restarts / self-corrections)
    from .korean import to_tts_text as _to_tts
    level = int(spec.get("disfluency", settings.get("default_disfluency", 0)) or 0)
    verbatim_text = script.spoken_text
    disfluency_edits: list[dict[str, Any]] = []
    if level > 0:
        verbatim_text, disfluency_edits = disfluency.apply(script.spoken_text, level, random.Random(seed + 11))
        if disfluency_edits:
            v_lines = verbatim_text.splitlines()
            script.tts_text = "\n".join([script.tts_text.splitlines()[0]] +
                                        [_to_tts(l, random.Random(seed + 13 + i)) for i, l in enumerate(v_lines[1:])])

    engine = get_engine(settings)
    voice_id = spec.get("voice_id") or ""
    voice_obj = voices_mod.get_voice(voice_id) if voice_id else None
    ref = voices_mod.pick_reference(voice_id, rng=rng, style="interview" if template_key == "s1" else "dictation") if voice_id else None
    if engine.clones_voice and ref is None:
        raise RuntimeError("목소리 복제 엔진에는 등록된 목소리(참조 음성)가 필요합니다. 목소리 등록 탭에서 먼저 녹음하세요.")

    paragraphs = [p for p in script.tts_text.splitlines() if p.strip()]
    spoken_lines = [p for p in script.spoken_text.splitlines() if p.strip()]
    if len(spoken_lines) != len(paragraphs):  # should not happen; labels then fall back to whole paragraphs
        spoken_lines = paragraphs
    t0 = time.perf_counter()
    chunk_verify = None
    if settings.get("asr_verify") and engine.clones_voice and verify_mod.available()[0]:
        chunk_verify = lambda sp, tt, a, sr_: verify_mod.chunk_cer(sp, tt, a, sr_, settings)  # noqa: E731
    patient_ref, patient_shift, patient_voice_name = None, (0.0, 1.0), ""
    if dialogue and len(speakers) == len(paragraphs) and "patient" in speakers:
        patient_ref, patient_shift, patient_voice_name = _patient_voice(spec, patient, voice_id, rng)
        audio, sr, segments = _synthesize_turns(engine, spoken_lines, paragraphs, speakers, {"nurse": ref, "patient": patient_ref or ref},
                                                {"patient": patient_shift if patient_ref is None else (0.0, patient_shift[1])}, seed, rng,
                                                progress=progress, verify=chunk_verify, cer_threshold=float(settings.get("chunk_cer_threshold", 0.3)),
                                                retries=int(settings.get("chunk_retries", 2)))
    else:
        audio, sr, segments = synthesize_script(engine, spoken_lines, paragraphs, ref, seed, progress=progress,
                                                verify=chunk_verify, cer_threshold=float(settings.get("chunk_cer_threshold", 0.3)),
                                                retries=int(settings.get("chunk_retries", 2)))
    timing: dict[str, Any] = {"synth_s": round(time.perf_counter() - t0, 1)}
    checked = [sg for sg in segments if "cer" in sg]
    chunk_summary = {"checked": len(checked), "retried": sum(1 for sg in checked if sg.get("retries")),
                     "still_bad": sum(1 for sg in checked if sg["cer"] > float(settings.get("chunk_cer_threshold", 0.3))),
                     "max_cer": max((sg["cer"] for sg in checked), default=None)} if checked else None
    audio = _loudness(normalize_peak(audio, 0.9), float(settings.get("loudness_dbfs", -20.0)))

    # --- voice preset (saved on the voice: pitch in semitones, tempo factor) makes one speaker several
    preset = {"pitch": float(getattr(voice_obj, "pitch", 0.0) or 0.0), "tempo": float(getattr(voice_obj, "tempo", 1.0) or 1.0)}
    if preset["pitch"]:
        audio = pitch_shift(audio, sr, preset["pitch"])
    if preset["tempo"] != 1.0:
        audio = time_stretch(audio, preset["tempo"])

    # --- channel / speed augmentation on the speech layer
    aug_cfg = _augment_cfg(spec.get("augment"))
    audio, aug_info = augment(audio, sr, aug_cfg, np.random.default_rng(seed + 17))

    extra_voices = []
    if spec.get("rounds_voice"):
        others = [v for v in voices_mod.list_voices() if v.id != voice_id and v.samples]
        if others and engine.clones_voice:
            other = rng.choice(others)
            oref = voices_mod.pick_reference(other.id, rng=rng)
            try:
                line = rng.choice(ROUNDS_LINES)
                oa, osr = engine.synthesize(line, oref, seed=seed + 99)
                if osr != sr:
                    oa = resample(oa, osr, sr)
                extra_voices.append((oa, other.name))
            except Exception:  # noqa: BLE001
                pass

    cfg = _noise_cfg(spec.get("noise"), settings, rng)
    if extra_voices and not cfg.enabled:
        cfg.enabled = True
        cfg.types = []
    t1 = time.perf_counter()
    mixed, events = mix(audio, sr, cfg, custom=custom_noises, extra_voices=extra_voices)
    timing["mix_s"] = round(time.perf_counter() - t1, 1)
    # segment times in the final file: speed perturbation stretches by 1/speed, the mixer pads the head
    scale = 1.0 / (float(aug_info.get("speed") or 1.0) * preset["tempo"])
    segments = [{**s, "start": round(s["start"] * scale + cfg.head_pad, 3), "end": round(s["end"] * scale + cfg.head_pad, 3)}
                for s in segments]

    out_sr = int(settings.get("sample_rate", 24000))
    if out_sr != sr:
        mixed = resample(mixed, sr, out_sr)
        sr = out_sr

    folder = Path(spec.get("folder") or output_dir())
    folder.mkdir(parents=True, exist_ok=True)
    base = make_basename(when, patient.name, folder)
    wav_path = folder / f"{base}.wav"
    txt_path = folder / f"{base}.txt"
    json_path = folder / f"{base}.json"
    write_wav(wav_path, mixed, sr)
    txt_path.write_text(script.spoken_text, encoding="utf-8")
    meta = {
        "file": wav_path.name,
        "signal": script.signal,
        "signal_format": script.structured.get("signal_format"),
        "signal_parse": __import__("nursing_tts.signal", fromlist=["parse"]).parse(script.spoken_text).to_dict(),
        "record_kind": get_template(template_key).signal_kind,
        "template": template_key,
        "datetime": when.isoformat(timespec="minutes"),
        "patient": patient.__dict__,
        "voice_id": voice_id,
        "ref_sample": Path(ref[0]).stem if ref else "",   # which reference clip was cloned; lets a deleted clip's recordings be found later
        "engine": engine.key,
        "clones_voice": engine.clones_voice,
        "style": style,
        "seed": seed,
        "llm_polished": polished,
        "spoken_text": script.spoken_text,
        "tts_text": script.tts_text,
        "sentences": script.sentences,
        "structured": script.structured,
        "noise": {"enabled": cfg.enabled, "level": cfg.level, "types": cfg.types, "events": events},
        "augment": aug_info,
        "voice_preset": preset,
        "disfluency_level": level,
        "disfluency_edits": disfluency_edits,
        "verbatim_text": verbatim_text,
        "segments": segments,  # sentence chunks with exact times (+ per-chunk Whisper CER when verification is on)
        "chunk_verify": chunk_summary,
        "dialogue": dialogue,
        "turns": script.turns,           # speaker per line (간호사/환자) for the labelled transcript
        "patient_voice_id": (spec.get("patient_voice_id") or "auto") if dialogue else "",
        "patient_voice_name": patient_voice_name,
        "patient_shift": {"pitch": patient_shift[0] if patient_ref is None else 0.0, "tempo": patient_shift[1]} if dialogue else None,

        "voice_name": voice_obj.name if voice_obj else "",
        "voice_sex": voice_obj.sex if voice_obj else "",
        "sample_rate": sr,
        "duration_sec": round(len(mixed) / sr, 2),
        "review": {"status": "pending", "note": ""},
    }
    if settings.get("asr_verify"):
        ok, _ = verify_mod.available()
        if ok:
            if progress:
                progress(len(paragraphs), len(paragraphs))
            t2 = time.perf_counter()
            meta["verify"] = verify_mod.verify(wav_path, script.spoken_text, script.tts_text, settings)
            timing["verify_s"] = round(time.perf_counter() - t2, 1)
        else:
            meta["verify"] = {"error": "faster-whisper 미설치", "passed": None}
    timing["total_s"] = round(time.perf_counter() - t_start, 1)
    timing["chunks"] = len(paragraphs)
    meta["timing"] = timing  # where the time goes (M3 throughput work)
    json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    if item is not None:
        item.files = {"wav": str(wav_path), "txt": str(txt_path), "json": str(json_path)}
        item.duration = meta["duration_sec"]
        item.spoken_text = script.spoken_text
        item.patient = patient.name
        item.template = template_key
        item.verify = meta.get("verify")
    return meta


def _trim_memory() -> None:
    """Between batch items: hand freed tensors back to the OS.  The MPS/CUDA caching allocator otherwise keeps growing — on the
    16 GB Mac the backend reached 17 GB and swapped after ~6 recordings, each one slower than the last (2026-10-17)."""
    import gc
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        elif hasattr(torch, "mps") and torch.backends.mps.is_available():
            torch.mps.empty_cache()
    except Exception:  # noqa: BLE001
        pass


def _run(job: Job, specs: list[dict[str, Any]], custom_noises: list[NoiseClip]) -> None:
    settings = load_settings()
    job.status = "running"
    for item, spec in zip(job.items, specs):
        if job.cancel:
            job.status = "cancelled"
            job.message = "취소됨"
            return
        item.status = "running"
        job.message = f"{item.index + 1}/{job.total} 생성 중"
        try:
            def prog(i, n, _item=item):
                job.message = f"{_item.index + 1}/{job.total} 생성 중 ({i}/{n} 문단)"
            generate_one(spec, settings, custom_noises, item=item, progress=prog)
            item.status = "done"
        except Exception as e:  # noqa: BLE001
            item.status = "error"
            item.error = f"{e}"
            traceback.print_exc()
            if job.kind == "single":
                job.status = "error"
                job.error = item.error
                return
        finally:
            _trim_memory()
    job.status = "done"
    job.message = "완료"


def start_single(spec: dict[str, Any], custom_noises: list[NoiseClip]) -> Job:
    """One form -> ``variants`` recordings with different seeds (and rotated voices)."""
    n = max(1, min(int(spec.get("variants") or 1), 20))
    rng = random.Random(spec.get("seed"))
    voice_ids = [v for v in (spec.get("voice_ids") or []) if v] or [spec.get("voice_id") or ""]
    specs = []
    for i in range(n):
        sp = dict(spec)
        if i > 0 or spec.get("seed") is None:
            sp["seed"] = rng.randrange(1 << 30)
        sp["voice_id"] = voice_ids[i % len(voice_ids)]
        specs.append(sp)
    job = Job(id=uuid.uuid4().hex[:8], kind="single" if n == 1 else "variants", total=n,
              items=[JobItem(index=i) for i in range(n)])
    with _LOCK:
        _JOBS[job.id] = job
    threading.Thread(target=_run, args=(job, specs, custom_noises), daemon=True).start()
    return job


def start_specs(base: list[dict[str, Any]], opts: dict[str, Any], custom_noises: list[NoiseClip]) -> Job:
    """Generate one recording per given spec (patient/form/datetime from an imported table), with the batch
    options for voice, noise, style, augmentation and folder."""
    rng = random.Random(opts.get("seed"))
    voice_ids = [v for v in (opts.get("voice_ids") or []) if v] or [""]
    noise = opts.get("noise") or {}
    noise_prob = float(opts.get("noise_prob", 0.5 if noise.get("enabled") else 0.0))
    folder = output_dir() if opts.get("no_folder") else \
        output_dir() / (safe_filename(opts.get("folder_name") or f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}"))
    specs = []
    for sp in base:
        n = dict(noise)
        n["enabled"] = bool(noise.get("enabled")) and rng.random() < noise_prob
        if n["enabled"] and noise.get("level_jitter", True):
            n["level"] = int(max(0, min(100, int(noise.get("level", 35)) + rng.randint(-15, 15))))
        dis = opts.get("disfluency")
        dis_level = int(dis) if dis not in (None, "", "random") else rng.choices([0, 1, 2, 3], weights=[40, 30, 20, 10])[0]
        specs.append({
            **sp, "style": opts.get("style") or sp.get("style") or "formal",
            "seed": sp.get("seed") if opts.get("keep_seed") and sp.get("seed") is not None else rng.randrange(1 << 30),   # a reviewed script is reproduced as read
            "voice_id": rng.choice(voice_ids), "noise": n, "llm_polish": bool(opts.get("llm_polish")),
            "rounds_voice": bool(opts.get("rounds_voice")) and rng.random() < 0.4, "folder": str(folder), "disfluency": dis_level,
            "augment": opts.get("augment") or {}, "signal_format": opts.get("signal_format") or "strict", "signal_aliases": opts.get("signal_aliases"),
        })
    job = Job(id=uuid.uuid4().hex[:8], kind="import", total=len(specs), items=[JobItem(index=i) for i in range(len(specs))], folder=str(folder))
    with _LOCK:
        _JOBS[job.id] = job
    threading.Thread(target=_run, args=(job, specs, custom_noises), daemon=True).start()
    return job


def start_batch(opts: dict[str, Any], custom_noises: list[NoiseClip]) -> Job:
    """opts: count, templates[], voice_ids[], noise{}, noise_prob, style, llm_polish, rounds_voice, folder_name."""
    count = max(1, min(int(opts.get("count", 10)), 2000))
    rng = random.Random(opts.get("seed"))
    templates = opts.get("templates") or ["s1", "s2", "s3_1", "s3_2", "s4", "s5"]
    voice_ids = opts.get("voice_ids") or [""]
    noise = opts.get("noise") or {}
    noise_prob = float(opts.get("noise_prob", 0.5 if noise.get("enabled") else 0.0))
    folder = output_dir() / (safe_filename(opts.get("folder_name") or f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"))
    specs = []
    for i in range(count):
        t = rng.choice(templates)
        patient = random_patient(rng, t)
        form = random_form(t, rng, patient)
        when = record_datetime(t, patient, form, rng)
        if t == "s1" and not opts.get("nursing_dx", True):
            form.pop("nursing_problems", None)          # 간호진단 문장 빼기 (user 2026-10-17)
        n = dict(noise)
        n["enabled"] = bool(noise.get("enabled")) and rng.random() < noise_prob
        if n["enabled"] and noise.get("level_jitter", True):
            n["level"] = int(max(0, min(100, int(noise.get("level", 35)) + rng.randint(-15, 15))))
        style = opts.get("style") or rng.choice(["formal", "formal", "formal", "mixed"])   # 격식체 위주 (user, 2026-10-16)
        dis = opts.get("disfluency")
        dis_level = int(dis) if dis not in (None, "", "random") else rng.choices([0, 1, 2, 3], weights=[40, 30, 20, 10])[0]
        specs.append({
            "template": t, "form": form, "patient": patient.__dict__, "datetime": when.isoformat(timespec="minutes"),
            "style": style, "seed": rng.randrange(1 << 30), "voice_id": rng.choice(voice_ids), "noise": n,
            "dialogue": bool(opts.get("dialogue_s1")) and t == "s1" and rng.random() < float(opts.get("dialogue_prob", 1.0)),
            "patient_voice_id": opts.get("patient_voice_id") or "auto",
            "llm_polish": bool(opts.get("llm_polish")), "rounds_voice": bool(opts.get("rounds_voice")) and rng.random() < 0.4,
            "folder": str(folder), "disfluency": dis_level, "augment": opts.get("augment") or {},
            "signal_format": opts.get("signal_format") or "random", "signal_aliases": opts.get("signal_aliases"),
        })
    job = Job(id=uuid.uuid4().hex[:8], kind="batch", total=count, items=[JobItem(index=i) for i in range(count)],
              folder=str(folder))
    with _LOCK:
        _JOBS[job.id] = job
    threading.Thread(target=_run, args=(job, specs, custom_noises), daemon=True).start()
    return job
