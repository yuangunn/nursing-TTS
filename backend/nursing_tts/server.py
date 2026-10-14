"""FastAPI backend used by the Electron UI."""
from __future__ import annotations

import io
import random
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

from . import __version__, dataset, jobs, llm, noise_library, verify as verify_mod, voices as voices_mod
from .audio.augment import preset_catalogue
from .audio import noise as noise_mod
from .audio.mixer import NoiseConfig, level_to_snr_db, mix
from .config import data_dir, load_settings, output_dir, save_settings
from .enroll_scripts import SCRIPTS
from .fake import random_datetime, random_form, random_patient
from .generator import Patient, build_script
from .templates import default_form, list_templates, TEMPLATES
from .tts.registry import engine_status

app = FastAPI(title="Nursing TTS backend", version=__version__)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class PatientModel(BaseModel):
    name: str = "홍길동"
    age: int | None = 64
    sex: str = "남"
    diagnosis: str = "위암"
    surgery: str = "Laparoscopic total gastrectomy"
    professor: str = "김민수"
    department: str = "외과"
    pod: int | None = 2
    op_date: str = ""
    admission_date: str = ""


class NoiseModel(BaseModel):
    enabled: bool = False
    level: int = 35
    types: list[str] = ["room_tone", "monitor_pulse", "crowd_babble", "footsteps"]
    density: float = 4.0
    reverb: bool = False


class PreviewRequest(BaseModel):
    template: str
    form: dict[str, Any] = {}
    patient: PatientModel = PatientModel()
    datetime: str | None = None
    style: str = "mixed"
    seed: int | None = None
    llm_polish: bool = False


class AugmentModel(BaseModel):
    enabled: bool = False
    channels: list[str] = ["studio", "smartphone", "lapel", "recorder"]
    speed_min: float = 0.92
    speed_max: float = 1.08
    speed_prob: float = 0.6
    gain_db_range: float = 6.0
    clip_prob: float = 0.1


class GenerateRequest(PreviewRequest):
    voice_id: str = ""
    voice_ids: list[str] = []          # rotate across these when variants > 1
    variants: int = 1
    noise: NoiseModel = NoiseModel()
    augment: AugmentModel = AugmentModel()
    disfluency: int = 0
    rounds_voice: bool = False
    text_override: str | None = None   # user-edited spoken text (ground truth)


class BatchRequest(BaseModel):
    count: int = 10
    templates: list[str] = ["s1", "s2", "s3_1", "s3_2", "s4", "s5"]
    voice_ids: list[str] = []
    noise: NoiseModel = NoiseModel()
    augment: AugmentModel = AugmentModel()
    disfluency: str | int | None = "random"
    noise_prob: float = 0.5
    style: str | None = None
    llm_polish: bool = False
    rounds_voice: bool = False
    folder_name: str = ""
    seed: int | None = None


class SettingsModel(BaseModel):
    tts_engine: str | None = None
    device: str | None = None
    f5_model: str | None = None
    f5_ckpt_file: str | None = None
    f5_vocab_file: str | None = None
    f5_nfe_step: int | None = None
    f5_speed: float | None = None
    http_tts_url: str | None = None
    output_dir: str | None = None
    sample_rate: int | None = None
    llm_provider: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None
    default_style: str | None = None
    noise_default_level: int | None = None
    asr_verify: bool | None = None
    asr_model: str | None = None
    asr_device: str | None = None
    cer_threshold: float | None = None
    loudness_dbfs: float | None = None
    default_disfluency: int | None = None


class ReviewRequest(BaseModel):
    rel: str
    status: str  # approved | rejected | pending
    note: str = ""


class ExportRequest(BaseModel):
    name: str = ""
    formats: list[str] = ["ljspeech", "nemo", "whisper", "csv"]
    split: dict[str, float] = {"train": 0.9, "val": 0.05, "test": 0.05}
    sample_rate: int = 16000
    include_fillers: bool = False
    only_approved: bool = False
    exclude_rejected: bool = True
    exclude_failed_verify: bool = True
    seed: int = 42


# ---------------------------------------------------------------------------
# Basics
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"ok": True, "version": __version__, "data_dir": str(data_dir()), "output_dir": str(output_dir())}


@app.get("/api/settings")
def get_settings():
    s = load_settings()
    s["_output_dir_resolved"] = str(output_dir())
    s["_data_dir"] = str(data_dir())
    masked = dict(s)
    if masked.get("llm_api_key"):
        masked["llm_api_key_set"] = True
        masked["llm_api_key"] = ""
    else:
        masked["llm_api_key_set"] = False
    return masked


@app.put("/api/settings")
def put_settings(body: SettingsModel):
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if "llm_api_key" in update and update["llm_api_key"] == "":
        update.pop("llm_api_key")  # keep existing key when field left blank
    save_settings(update)
    return get_settings()


@app.delete("/api/settings/llm_api_key")
def clear_api_key():
    save_settings({"llm_api_key": ""})
    return {"ok": True}


@app.get("/api/engines")
def engines():
    s = load_settings()
    ok, msg = verify_mod.available()
    return {"selected": s.get("tts_engine", "auto"), "engines": engine_status(s), "asr": {"available": ok, "status": msg}}


@app.get("/api/augment/presets")
def augment_presets():
    return preset_catalogue()


@app.post("/api/disfluency/preview")
def disfluency_preview(body: dict[str, Any]):
    from .disfluency import apply
    text, edits = apply(body.get("text", ""), int(body.get("level", 1)), random.Random(body.get("seed")))
    return {"text": text, "edits": edits}


# ---------------------------------------------------------------------------
# Recordings (QA review) & dataset export
# ---------------------------------------------------------------------------

@app.get("/api/recordings")
def recordings(limit: int = 2000):
    return {"folder": str(output_dir()), "items": dataset.list_recordings(limit)}


@app.get("/api/recordings/meta")
def recording_meta(rel: str):
    try:
        return dataset.load_meta(rel)
    except FileNotFoundError:
        raise HTTPException(404, "not found")


@app.post("/api/recordings/review")
def recording_review(body: ReviewRequest):
    if body.status not in ("approved", "rejected", "pending"):
        raise HTTPException(400, "bad status")
    try:
        return dataset.set_review(body.rel, body.status, body.note)
    except FileNotFoundError:
        raise HTTPException(404, "not found")


@app.delete("/api/recordings")
def recording_delete(rel: str):
    try:
        dataset.delete_recording(rel)
    except FileNotFoundError:
        raise HTTPException(404, "not found")
    return {"ok": True}


@app.post("/api/recordings/verify")
def recording_verify(body: dict[str, Any]):
    """Run (or re-run) ASR verification for one recording."""
    ok, msg = verify_mod.available()
    if not ok:
        raise HTTPException(400, msg)
    try:
        meta = dataset.load_meta(body["rel"])
        p = output_dir() / body["rel"]
    except (FileNotFoundError, KeyError):
        raise HTTPException(404, "not found")
    meta["verify"] = verify_mod.verify(p, meta.get("spoken_text", ""), meta.get("tts_text", ""), load_settings())
    p.with_suffix(".json").write_text(__import__("json").dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta["verify"]


@app.post("/api/dataset/export")
def dataset_export(body: ExportRequest):
    try:
        return dataset.export(body.model_dump())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"내보내기 실패: {e}")


@app.post("/api/noises/import-folder")
def noises_import_folder(body: dict[str, Any]):
    """Import every audio file in a folder (e.g. MUSAN / DEMAND / own ward recordings)."""
    folder = Path(body.get("path", ""))
    if not folder.is_dir():
        raise HTTPException(400, "폴더를 찾을 수 없습니다")
    added, failed = [], []
    sr = int(load_settings().get("sample_rate", 24000))
    for p in sorted(folder.rglob("*")):
        if p.suffix.lower() not in (".wav", ".flac", ".ogg", ".mp3", ".aiff", ".aif"):
            continue
        try:
            added.append(noise_library.add_custom(p, p.stem, bool(body.get("continuous", False)),
                                                  float(body.get("gain", 0.5)), sr=sr))
        except Exception as e:  # noqa: BLE001
            failed.append({"file": p.name, "error": str(e)})
        if len(added) >= int(body.get("limit", 200)):
            break
    return {"added": added, "failed": failed}


# ---------------------------------------------------------------------------
# Templates & script preview
# ---------------------------------------------------------------------------

@app.get("/api/templates")
def templates():
    return list_templates()


@app.get("/api/templates/{key}/defaults")
def template_defaults(key: str):
    if key not in TEMPLATES:
        raise HTTPException(404, "unknown template")
    return default_form(key)


@app.post("/api/script/preview")
def preview(req: PreviewRequest):
    if req.template not in TEMPLATES:
        raise HTTPException(404, "unknown template")
    when = datetime.fromisoformat(req.datetime) if req.datetime else datetime.now().replace(second=0, microsecond=0)
    script = build_script(req.template, req.form, Patient(**req.patient.model_dump()), when, style=req.style, seed=req.seed)
    spoken = script.spoken_text
    polished = False
    if req.llm_polish:
        try:
            new = llm.polish(spoken, load_settings())
            polished = new != spoken
            spoken = new
        except Exception as e:  # noqa: BLE001
            raise HTTPException(502, f"LLM 호출 실패: {e}")
    return {"spoken_text": spoken, "tts_text": script.tts_text, "signal": script.signal, "seed": script.seed,
            "sentences": script.sentences, "llm_polished": polished,
            "filename": f"{when.strftime('%Y%m%d_%H%M')}_{jobs.safe_filename(req.patient.name)}"}


@app.post("/api/random-patient")
def random_patient_api(body: dict[str, Any]):
    rng = random.Random(body.get("seed"))
    t = body.get("template") or "s1"
    p = random_patient(rng, t)
    form = random_form(t, rng, p)
    when = random_datetime(rng)
    return {"patient": p.__dict__, "form": form, "datetime": when.isoformat(timespec="minutes")}


# ---------------------------------------------------------------------------
# Generation jobs
# ---------------------------------------------------------------------------

@app.post("/api/generate")
def generate(req: GenerateRequest):
    if req.template not in TEMPLATES:
        raise HTTPException(404, "unknown template")
    spec = req.model_dump()
    job = jobs.start_single(spec, noise_library.custom_clips())
    return job.to_dict()


@app.post("/api/batch")
def batch(req: BatchRequest):
    job = jobs.start_batch(req.model_dump(), noise_library.custom_clips())
    return job.to_dict()


@app.get("/api/jobs")
def jobs_list():
    return jobs.list_jobs()


@app.get("/api/jobs/{job_id}")
def job_get(job_id: str):
    j = jobs.get_job(job_id)
    if not j:
        raise HTTPException(404, "no such job")
    return j.to_dict()


@app.post("/api/jobs/{job_id}/cancel")
def job_cancel(job_id: str):
    return {"ok": jobs.cancel_job(job_id)}


@app.get("/api/output")
def output_list(limit: int = 200):
    folder = output_dir()
    files = sorted(folder.rglob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    out = []
    for p in files:
        out.append({"name": p.name, "rel": str(p.relative_to(folder)), "size": p.stat().st_size,
                    "mtime": p.stat().st_mtime, "has_json": p.with_suffix(".json").exists()})
    return {"folder": str(folder), "files": out}


@app.get("/api/output/file")
def output_file(rel: str):
    folder = output_dir().resolve()
    p = (folder / rel).resolve()
    if folder not in p.parents and p != folder or not p.exists():
        raise HTTPException(404, "not found")
    return FileResponse(str(p))


@app.get("/api/output/meta")
def output_meta(rel: str):
    folder = output_dir().resolve()
    p = (folder / rel).resolve().with_suffix(".json")
    if folder not in p.parents or not p.exists():
        raise HTTPException(404, "not found")
    return JSONResponse(content=__import__("json").loads(p.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# Voices
# ---------------------------------------------------------------------------

@app.get("/api/enroll-scripts")
def enroll_scripts():
    return SCRIPTS


@app.get("/api/voices")
def voices_list():
    return [v.to_dict() for v in voices_mod.list_voices()]


@app.post("/api/voices")
def voices_create(body: dict[str, Any]):
    v = voices_mod.create_voice(body.get("name", ""), body.get("note", ""), body.get("sex", ""))
    return v.to_dict()


@app.patch("/api/voices/{voice_id}")
def voices_update(voice_id: str, body: dict[str, Any]):
    try:
        return voices_mod.update_voice(voice_id, **body).to_dict()
    except KeyError:
        raise HTTPException(404, "no such voice")


@app.delete("/api/voices/{voice_id}")
def voices_delete(voice_id: str):
    voices_mod.delete_voice(voice_id)
    return {"ok": True}


@app.post("/api/voices/{voice_id}/samples")
async def voices_add_sample(voice_id: str, file: UploadFile = File(...), transcript: str = Form(""),
                            script_id: str = Form("")):
    if not voices_mod.get_voice(voice_id):
        raise HTTPException(404, "no such voice")
    suffix = Path(file.filename or "sample.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
    try:
        s = voices_mod.add_sample(voice_id, tmp_path, transcript, script_id, target_sr=int(load_settings().get("sample_rate", 24000)))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"오디오 파일을 읽을 수 없습니다: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)
    return {"sample": s.__dict__, "voice": voices_mod.get_voice(voice_id).to_dict()}


@app.delete("/api/voices/{voice_id}/samples/{sample_id}")
def voices_delete_sample(voice_id: str, sample_id: str):
    try:
        return voices_mod.delete_sample(voice_id, sample_id).to_dict()
    except KeyError:
        raise HTTPException(404, "no such voice")


@app.get("/api/voices/{voice_id}/samples/{sample_id}/audio")
def voices_sample_audio(voice_id: str, sample_id: str):
    p = voices_mod.sample_path(voice_id, sample_id)
    if not p or not p.exists():
        raise HTTPException(404, "not found")
    return FileResponse(str(p), media_type="audio/wav")


@app.post("/api/voices/{voice_id}/test")
def voices_test(voice_id: str, body: dict[str, Any]):
    """Quick cloning test: synthesise one sentence with this voice."""
    text = body.get("text") or "안녕하세요, 목소리 등록 테스트입니다. 혈압은 123에 90 나오셨구요, 맥박은 72입니다."
    spec = {"template": "s5", "form": {}, "patient": {"name": "테스트"}, "voice_id": voice_id, "noise": {"enabled": False}}
    # Use a tiny direct synthesis rather than the full template path.
    from .korean import to_tts_text
    from .tts.registry import get_engine
    settings = load_settings()
    engine = get_engine(settings)
    ref = voices_mod.pick_reference(voice_id, prefer_primary=True)
    if engine.clones_voice and ref is None:
        raise HTTPException(400, "이 목소리에 등록된 샘플이 없습니다.")
    try:
        audio, sr = engine.synthesize(to_tts_text(text, random.Random(1)), ref, seed=1)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"합성 실패 ({engine.label}): {e}")
    buf = io.BytesIO()
    sf.write(buf, np.clip(audio, -1, 1), sr, format="WAV", subtype="PCM_16")
    return Response(content=buf.getvalue(), media_type="audio/wav",
                    headers={"X-Engine": engine.key, "X-Clones-Voice": str(engine.clones_voice)})


# ---------------------------------------------------------------------------
# Noise library
# ---------------------------------------------------------------------------

@app.get("/api/noises")
def noises():
    return noise_library.catalogue()


@app.post("/api/noises")
async def noises_add(file: UploadFile = File(...), label: str = Form(""), continuous: bool = Form(False),
                     gain: float = Form(0.5)):
    suffix = Path(file.filename or "noise.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
    try:
        item = noise_library.add_custom(tmp_path, label or Path(file.filename or "noise").stem, continuous, gain,
                                        sr=int(load_settings().get("sample_rate", 24000)))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"오디오 파일을 읽을 수 없습니다 (wav/flac/ogg/mp3 지원): {e}")
    finally:
        tmp_path.unlink(missing_ok=True)
    return item


@app.patch("/api/noises/{nid}")
def noises_update(nid: str, body: dict[str, Any]):
    item = noise_library.update_custom(nid, **body)
    if not item:
        raise HTTPException(404, "not found")
    return item


@app.delete("/api/noises/{nid}")
def noises_delete(nid: str):
    if not noise_library.delete_custom(nid):
        raise HTTPException(404, "not found")
    return {"ok": True}


@app.get("/api/noises/{key}/preview")
def noises_preview(key: str, seconds: float = 6.0):
    sr = 24000
    if key in noise_mod.BUILTIN:
        rng = np.random.default_rng()
        nt = noise_mod.BUILTIN[key]
        dur = float(seconds) if nt.continuous else max(min(float(seconds), nt.max_dur), nt.min_dur)
        audio = noise_mod.render(key, dur, sr, rng) * 0.8
    else:
        p = noise_library.custom_path(key)
        if not p:
            raise HTTPException(404, "not found")
        return FileResponse(str(p), media_type="audio/wav")
    buf = io.BytesIO()
    sf.write(buf, np.clip(audio, -1, 1), sr, format="WAV", subtype="PCM_16")
    return Response(content=buf.getvalue(), media_type="audio/wav")


@app.post("/api/noises/preview-mix")
def noises_preview_mix(body: NoiseModel):
    """Preview the ambience bed alone (no speech) with the chosen settings."""
    sr = 24000
    speech = np.zeros(int(8 * sr), dtype=np.float32)
    cfg = NoiseConfig(enabled=True, level=body.level, types=body.types, density=max(body.density, 8.0),
                      reverb=body.reverb, seed=None, head_pad=0, tail_pad=0)
    # use a fake speech RMS so the SNR scaling has something to work against
    tone = 0.1 * np.sin(2 * np.pi * 200 * np.arange(len(speech)) / sr).astype(np.float32)
    mixed, events = mix(tone, sr, cfg, custom=noise_library.custom_clips())
    mixed = mixed - tone[: len(mixed)] if len(mixed) == len(tone) else mixed
    buf = io.BytesIO()
    sf.write(buf, np.clip(mixed, -1, 1), sr, format="WAV", subtype="PCM_16")
    return Response(content=buf.getvalue(), media_type="audio/wav", headers={"X-SNR-dB": f"{level_to_snr_db(body.level):.1f}"})
