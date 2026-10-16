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

from . import __version__, dataset, jobs, llm, noise_library, phrase_store, script_review, signal as signal_mod, verify as verify_mod, voices as voices_mod
from .templates.extra_phrases import VITALS_FORMS
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
    diagnosis: str = "담낭염"
    surgery: str = "Lapa chole"
    professor: str = "김민수"
    department: str = "외과"
    pod: int | None = 2
    op_date: str = ""
    admission_date: str = ""
    kind: str = "op"               # op | chemo
    regimen: str = ""
    cycle: int | None = None
    day: int | None = None
    scenario: str = ""


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
    style: str = "formal"
    seed: int | None = None
    llm_polish: bool = False
    signal_format: str | None = None   # strict | <key> | random | literal template; None -> settings default
    signal_aliases: bool | None = None


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
    signal_format: str = "random"
    signal_aliases: bool | None = None
    noise_prob: float = 0.5
    style: str | None = None
    llm_polish: bool = False
    rounds_voice: bool = False
    folder_name: str = ""
    seed: int | None = None


class SettingsModel(BaseModel):
    tts_engine: str | None = None
    device: str | None = None
    qwen_model: str | None = None
    qwen_idle_unload_min: int | None = None
    qwen_batch: int | None = None
    http_tts_url: str | None = None
    output_dir: str | None = None
    sample_rate: int | None = None
    llm_provider: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None
    default_style: str | None = None
    noise_default_level: int | None = None
    floor_dbfs: float | None = None
    room_wet: float | None = None
    asr_verify: bool | None = None
    asr_model: str | None = None
    asr_device: str | None = None
    cer_threshold: float | None = None
    chunk_cer_threshold: float | None = None
    chunk_retries: int | None = None
    loudness_dbfs: float | None = None
    default_disfluency: int | None = None
    auto_style_expand: bool | None = None
    signal_format: str | None = None
    signal_aliases: bool | None = None
    rounds_shift: dict[str, float] | None = None
    rounds_tempo: dict[str, float] | None = None
    rounds_tempo_jitter: float | None = None


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
    max_clip_sec: float = 0            # >0: cut long recordings at sentence segments (30 for Whisper fine-tuning)


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
# Phrase library (view / manage spoken variants per element)
# ---------------------------------------------------------------------------

def _phrase_tree() -> list[dict[str, Any]]:
    out = []
    for key, t in TEMPLATES.items():
        sections = []
        for sec in t.sections:
            fields = []
            for f in sec.fields:
                slots = []
                if f.kind in ("select",):
                    for o in f.options:
                        slots.append({"slot": o.value, "label": o.label, "builtin": o.phrases,
                                      "override": phrase_store.get_override(key, f.key, o.value)})
                elif f.kind == "multi":
                    slots.append({"slot": "phrases", "label": "선택 항목 나열 ({v})", "builtin": f.phrases,
                                  "override": phrase_store.get_override(key, f.key, "phrases")})
                    slots.append({"slot": "none", "label": "해당 없음일 때", "builtin": f.none_phrases,
                                  "override": phrase_store.get_override(key, f.key, "none")})
                elif f.kind == "bool":
                    slots.append({"slot": "phrases", "label": "체크했을 때", "builtin": f.phrases,
                                  "override": phrase_store.get_override(key, f.key, "phrases")})
                    slots.append({"slot": "false", "label": "체크 안 했을 때", "builtin": f.false_phrases,
                                  "override": phrase_store.get_override(key, f.key, "false")})
                elif f.kind == "vitals":
                    continue
                else:
                    slots.append({"slot": "phrases", "label": "값 삽입 문장 ({v})", "builtin": f.phrases,
                                  "override": phrase_store.get_override(key, f.key, "phrases")})
                fields.append({"key": f.key, "label": f.label, "kind": f.kind, "unit": f.unit, "placeholder": f.placeholder,
                               "example": f.example, "slots": slots})
            sections.append({"key": sec.key, "title": sec.title, "fields": fields})
        meta = [
            {"key": "intros", "label": "도입부 (시그널 다음 문장)", "kind": "meta", "slots": [{"slot": "phrases", "label": "변형", "builtin": t.intros, "override": phrase_store.get_override(key, "intros", "phrases")}]},
            {"key": "closings", "label": "종료 문장", "kind": "meta", "slots": [{"slot": "phrases", "label": "변형", "builtin": t.closings, "override": phrase_store.get_override(key, "closings", "phrases")}]},
        ]
        sections.insert(0, {"key": "_meta", "title": "도입·종료", "fields": meta})
        out.append({"key": key, "title": t.title, "sections": sections})
    vitals = {"key": "_vitals", "title": "활력징후 읽기 형식 (모든 템플릿 공통)", "sections": [{"key": "vitals", "title": "V/S", "fields": [
        {"key": k, "label": label, "kind": "vitals_form", "slots": [{"slot": "phrases", "label": "형식", "builtin": VITALS_FORMS[k], "override": phrase_store.get_override("_vitals", k, "phrases")}]}
        for k, label in [("lead", "앞머리 (활력징후는…)"), ("bp", "혈압 {sbp} {dbp}"), ("hr", "맥박 {hr}"), ("rr", "호흡 {rr}"), ("bt", "체온 {bt} / {bt_casual}"),
                         ("spo2", "산소포화도 {spo2}"), ("o2_with", "산소 적용 중 ({o2}, {base})"), ("o2_room", "room air ({base})"), ("ending", "맺음말 (혼합)"), ("ending_formal", "맺음말 (격식)")]]}]}
    out.append(vitals)
    out.append({"key": "_signal", "title": "시그널(녹음 시작 문장) 형식", "sections": [{"key": "signal", "title": "형식", "fields": [
        {"key": "formats", "label": "시그널 템플릿 ({date} {time} {name} {kind})", "kind": "signal",
         "slots": [{"slot": "phrases", "label": "형식 목록 (무작위 모드에서 사용)", "builtin": signal_mod.builtin_written_templates(),
                    "override": phrase_store.get_override("_signal", "formats", "phrases")}]}]}]})
    return out


class PhraseUpdate(BaseModel):
    template: str
    field: str
    slot: str
    phrases: list[str]


@app.get("/api/phrases")
def phrases_tree():
    ok = bool(load_settings().get("auto_style_expand", True))
    tree = _phrase_tree()
    total = 0
    overridden = 0
    for t in tree:
        for sec in t["sections"]:
            for f in sec["fields"]:
                for sl in f["slots"]:
                    total += len(sl["override"] if sl["override"] is not None else sl["builtin"])
                    overridden += 1 if sl["override"] is not None else 0
    return {"templates": tree, "auto_style_expand": ok, "total_variants": total, "effective_variants": total * (3 if ok else 1),
            "overridden_slots": overridden}


@app.put("/api/phrases")
def phrases_set(body: PhraseUpdate):
    phrase_store.set_override(body.template, body.field, body.slot, body.phrases)
    return {"ok": True, "override": phrase_store.get_override(body.template, body.field, body.slot)}


@app.delete("/api/phrases")
def phrases_reset(template: str, field: str | None = None, slot: str | None = None):
    phrase_store.reset_override(template, field, slot)
    return {"ok": True}


@app.get("/api/phrases/export")
def phrases_export():
    return phrase_store.all_overrides()


@app.post("/api/phrases/import")
def phrases_import(body: dict[str, Any]):
    n = phrase_store.import_overrides(body.get("data") or {}, replace=bool(body.get("replace", False)))
    return {"ok": True, "slots": n}


@app.post("/api/phrases/sample")
def phrases_sample(body: dict[str, Any]):
    """Render a few example sentences for one element (with the style expander applied)."""
    from .generator import Patient as _P, realize_field
    from .templates.base import Field as _F
    template = body.get("template", "")
    field_key = body.get("field", "")
    slot = body.get("slot", "phrases")
    phrases = [p for p in (body.get("phrases") or []) if p and p.strip()]
    style = body.get("style", "formal")
    rng = random.Random(body.get("seed"))
    ctx = _P(op_date="10월 14일").context(rng)
    ctx["_template"] = template
    ctx.update({"drain_amount": 20, "bt_peak": 37.4, "bt_now": 36.9, "sbp": 123, "dbp": 78, "hr": 72, "event": "발열"})
    samples: list[str] = []
    if template == "_signal":
        from datetime import datetime as _dt
        tpls = [p for p in phrases if "{name}" in p] or signal_mod.builtin_written_templates()
        for _ in range(4):
            w, _t, _k = signal_mod.render(_dt(2026, 10, 12, 21, 42), "강신자", "간호정보조사", rng.choice(tpls), rng)
            samples.append(w + ("  ✔ 파서 인식" if signal_mod.parse(w).ok else "  ✖ 파서가 못 잡음"))
        return {"samples": samples}
    if template == "_vitals":
        from .generator import realize_vitals
        v = {"sbp": 123, "dbp": 78, "hr": 72, "rr": 18, "bt": 37.1, "spo2": 97, "o2": "room air"}
        for _ in range(4):
            samples.append(realize_vitals(v, rng, style))
        return {"samples": samples}
    if field_key in ("intros", "closings"):
        from .generator import _fmt
        from .grammar import fix_josa
        for _ in range(min(4, len(phrases)) or 1):
            samples.append(fix_josa(_fmt(rng.choice(phrases), ctx)) if phrases else "")
        return {"samples": samples}
    t = TEMPLATES.get(template)
    f = t.field_map().get(field_key) if t else None
    if f is None:
        raise HTTPException(404, "unknown field")
    # Build a temporary field whose list is replaced by the candidate phrases.
    import copy
    tmp: _F = copy.deepcopy(f)
    value: Any
    if f.kind == "select":
        o = next((o for o in tmp.options if o.value == slot), None)
        if o is None:
            raise HTTPException(404, "unknown option")
        o.phrases = phrases
        value = slot
    elif f.kind == "multi":
        if slot == "none":
            tmp.none_phrases = phrases
            value = ["none"]
        else:
            tmp.phrases = phrases
            real = [o.value for o in tmp.options if o.value != "none"]
            value = real[:2]
    elif f.kind == "bool":
        if slot == "false":
            tmp.false_phrases = phrases
            value = False
        else:
            tmp.phrases = phrases
            value = True
    elif f.kind == "number":
        tmp.phrases = phrases
        value = f.default if f.default is not None else 3
    else:
        tmp.phrases = phrases
        value = f.default or (f.placeholder.replace("예: ", "") if f.placeholder else "예시 값")
    tmp.speak_prob = 1.0
    phrase_store_backup = phrase_store.get_override(template, field_key, slot)
    try:
        phrase_store.set_override(template, field_key, slot, phrases)
        for _ in range(4):
            out = realize_field(tmp, value, ctx, rng, style, force_close=(_ % 2 == 1))
            samples.append(out or "")
    finally:
        if phrase_store_backup is None:
            phrase_store.reset_override(template, field_key, slot)
        else:
            phrase_store.set_override(template, field_key, slot, phrase_store_backup)
    return {"samples": samples}


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


@app.get("/api/scenarios")
def scenarios():
    """Ward surgeries and chemo regimens from the knowledge base (for the patient panel's pick lists)."""
    from .clinical import SCENARIOS
    return [{"key": s.key, "ko": s.ko, "abbr": s.abbr, "dept": s.dept, "kind": s.kind} for s in SCENARIOS]


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
    st = load_settings()
    script = build_script(req.template, req.form, Patient(**req.patient.model_dump()), when, style=req.style, seed=req.seed,
                          signal_format=req.signal_format or st.get("signal_format", "strict"),
                          signal_aliases=bool(st.get("signal_aliases", False) if req.signal_aliases is None else req.signal_aliases))
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
            "signal_format": script.structured.get("signal_format"), "signal_parse": script.structured.get("signal_parse"),
            "filename": f"{when.strftime('%Y%m%d_%H%M')}_{jobs.safe_filename(req.patient.name)}"}


@app.get("/api/script-review")
def script_review_list():
    items = script_review.load()
    return {"items": items, "markdown": script_review.as_markdown(items)}


@app.post("/api/script-review")
def script_review_add(body: dict[str, Any]):
    if not (body.get("sentence") or "").strip():
        raise HTTPException(400, "문장이 비어 있습니다.")
    return script_review.add(body)


@app.patch("/api/script-review/{flag_id}")
def script_review_update(flag_id: str, body: dict[str, Any]):
    it = script_review.update(flag_id, body.get("note", ""))
    if not it:
        raise HTTPException(404, "no such flag")
    return it


@app.delete("/api/script-review/{flag_id}")
def script_review_delete(flag_id: str):
    return {"removed": script_review.remove(flag_id)}


@app.delete("/api/script-review")
def script_review_clear():
    return {"removed": script_review.remove(None)}


@app.get("/api/signal/formats")
def signal_formats():
    custom = phrase_store.get_override("_signal", "formats", "phrases") or []
    return {"formats": signal_mod.FORMATS, "custom": [c for c in custom if "{name}" in c],
            "kind_aliases": signal_mod.KIND_ALIASES, "default": load_settings().get("signal_format", "strict")}


@app.post("/api/signal/parse")
def signal_parse(body: dict[str, Any]):
    """Tolerant trigger detection: finds date/time/name/kind/verb in any text (first ~200 chars)."""
    return signal_mod.parse(body.get("text", "")).to_dict()


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


@app.post("/api/voices/{voice_id}/samples/from-long")
async def voices_from_long(voice_id: str, file: UploadFile = File(...), max_clips: int = Form(8),
                           transcribe: bool = Form(True)):
    """Cut a long narration (2-3 min) into 6-14 s reference clips, transcribing each when Whisper is available."""
    if not voices_mod.get_voice(voice_id):
        raise HTTPException(404, "no such voice")
    from . import slicer
    suffix = Path(file.filename or "long.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
    settings = load_settings()
    try:
        clips = slicer.process(tmp_path, sr=int(settings.get("sample_rate", 24000)), transcribe=transcribe,
                               max_clips=max(1, min(int(max_clips), 30)), model_size=settings.get("asr_model") or "small",
                               device=settings.get("asr_device") or "auto")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"오디오를 읽거나 자를 수 없습니다: {e}")
    finally:
        tmp_path.unlink(missing_ok=True)
    added = []
    for c in clips:
        s = voices_mod.add_sample_array(voice_id, c.audio, int(settings.get("sample_rate", 24000)), c.transcript,
                                        script_id="auto")
        added.append({**s.__dict__, "start": round(c.start, 2), "end": round(c.end, 2)})
    ok, _ = verify_mod.available()
    return {"added": added, "transcribed": ok and transcribe, "voice": voices_mod.get_voice(voice_id).to_dict()}


@app.patch("/api/voices/{voice_id}/samples/{sample_id}")
def voices_update_sample(voice_id: str, sample_id: str, body: dict[str, Any]):
    v = voices_mod.get_voice(voice_id)
    if not v:
        raise HTTPException(404, "no such voice")
    for smp in v.samples:
        if smp.id == sample_id:
            if "transcript" in body:
                smp.transcript = str(body["transcript"]).strip()
            voices_mod._save(v)
            return smp.__dict__
    raise HTTPException(404, "no such sample")


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


@app.get("/api/voices/{voice_id}/demo")
def voices_demo(voice_id: str, pitch: float | None = None, tempo: float | None = None):
    """A synthesised demo of one fixed sentence: the bundled clip if the app ships one for this voice, else a
    per-voice cache, else synthesised now. The source recordings themselves are not played back when choosing
    a voice. ``pitch`` (semitones) and ``tempo`` (rate) let the user hear the voice shifted."""
    voice = voices_mod.get_voice(voice_id)
    if not voice:
        raise HTTPException(404, "목소리가 없습니다.")
    pitch = voice.pitch if pitch is None else pitch      # no query → the voice's saved preset
    tempo = voice.tempo if tempo is None else tempo
    path = voices_mod.bundled_demo(voice_id) or voices_mod.demo_path(voice_id)
    if not path.exists():
        from .korean import to_tts_text
        from .tts.registry import get_engine
        engine = get_engine(load_settings())
        ref = voices_mod.pick_reference(voice_id, prefer_primary=True)
        if engine.clones_voice and ref is None:
            raise HTTPException(400, "이 목소리에 등록된 샘플이 없습니다.")
        try:
            audio, sr = engine.synthesize(to_tts_text(voices_mod.DEMO_TEXT, random.Random(1)), ref, seed=1)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(500, f"합성 실패 ({engine.label}): {e}")
        sf.write(path, np.clip(audio, -1, 1), sr, format="WAV", subtype="PCM_16")
    pitch = max(-12.0, min(12.0, float(pitch)))
    tempo = max(0.5, min(2.0, float(tempo)))
    if path.suffix == ".wav" and pitch == 0 and tempo == 1:
        return Response(content=path.read_bytes(), media_type="audio/wav", headers={"Cache-Control": "no-store"})
    from .audio.io import read_audio
    from .rounds import pitch_shift, time_stretch
    audio, sr = read_audio(path, 24000)
    if pitch:
        audio = pitch_shift(audio, sr, pitch)
    if tempo != 1:
        audio = time_stretch(audio, tempo)
    buf = io.BytesIO()
    sf.write(buf, np.clip(audio, -1, 1), sr, format="WAV", subtype="PCM_16")
    return Response(content=buf.getvalue(), media_type="audio/wav", headers={"Cache-Control": "no-store"})


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
        raise HTTPException(400, f"오디오 파일을 읽을 수 없습니다 (wav/flac/ogg/mp3/m4a 지원, m4a·mp3는 ffmpeg 필요): {e}")
    finally:
        tmp_path.unlink(missing_ok=True)
    return item


@app.post("/api/noises/rounds")
def noises_rounds(body: dict[str, Any] | None = None):
    """Script a short doctor-rounds exchange, read it with a registered voice (pitch-shifted per role)
    or the OS TTS, and save it as a far-away noise clip."""
    from .audio.io import write_wav
    from .rounds import render
    from .tts.registry import get_engine
    from .tts.system import SystemTTSEngine

    body = body or {}
    rng = random.Random(body.get("seed"))
    settings = load_settings()
    sr = int(settings.get("sample_rate", 24000))
    engine = get_engine(settings)
    ref = None
    label = "회진 대화 (시스템 TTS, 멀리서)"
    if engine.clones_voice:
        voice_id = body.get("voice_id") or next((v.id for v in voices_mod.list_voices() if v.samples), "")
        voice = voices_mod.get_voice(voice_id) if voice_id else None
        if voice and voice.samples:
            ref = voices_mod.pick_reference(voice_id, rng=rng)
            label = f"회진 대화 ({voice.name} 톤 변조, 멀리서)"
    if ref is None:
        engine = SystemTTSEngine()
        ok, status = engine.available()
        if not ok:
            raise HTTPException(400, f"시스템 TTS를 쓸 수 없습니다 ({status})")
    audio, dialogue = render(engine, rng, sr=sr, turns=int(body.get("turns", 6)), ref=ref,
                             shift=body.get("shift") or settings.get("rounds_shift"),
                             tempo=body.get("tempo") or settings.get("rounds_tempo"),
                             jitter=float(settings.get("rounds_tempo_jitter", 0.08)))
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp_path = Path(tmp.name)
    try:
        write_wav(tmp_path, audio, sr)
        item = noise_library.add_custom(tmp_path, body.get("label") or label, False, 0.6, sr=sr)
    finally:
        tmp_path.unlink(missing_ok=True)
    item["dialogue"] = [f"{r}: {t}" for r, t in dialogue]
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
