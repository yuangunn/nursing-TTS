"""목소리 학습: one speaker's clips -> a LoRA adapter on the built-in Qwen3-TTS Base model.

Data layout and loss are the official single-speaker recipe (QwenLM/Qwen3-TTS ``finetuning/``, Apache-2.0). That
script trains every weight (1.7B: ~16 GB of weights, gradients and Adam state - more than a 16 GB Mac or a 12 GB GPU
holds), so here the base stays frozen and only rank-r adapters on the talker's attention/MLP projections train
(2026-10-19 on an M4: ~5 GB, ~1 min per epoch for 6 min of audio). Only the adapter and the speaker embedding are
saved (tens of MB, not a 4.5 GB model per nurse); the engine puts them on the same base model when that voice speaks.

Layout under ``data_dir()/finetune``: ``datasets/<id>/{dataset.json, clips/*.wav}`` and
``models/<id>/{config.json, progress.jsonl, train.log, adapter.pt}``. Training runs in a child process
(``python -m nursing_tts.finetune <model dir>``) so its memory goes back to the OS when it ends and a crash
cannot take the backend down.
"""
from __future__ import annotations

import contextlib
import json
import math
import os
import random
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import numpy as np

from .audio.io import read_audio, write_wav
from .config import data_dir

SR = 24000
PAD_S = 0.25          # silence around a registered clip: registration cut them tight (2026-10-19)
SPEAKER = "nurse"     # the one speaker a fine-tuned voice carries (slot 3000, as in the official recipe)
SPK_ID = 3000
TARGET = ("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj")
DEFAULTS: dict[str, Any] = {"epochs": 8, "lr": 1e-4, "rank": 16, "accum": 8}
MIN_ITEMS = 5


def root() -> Path:
    p = data_dir() / "finetune"
    (p / "datasets").mkdir(parents=True, exist_ok=True)
    (p / "models").mkdir(parents=True, exist_ok=True)
    return p


def model_dir(model_id: str) -> Path:
    return root() / "models" / model_id


# ---------------------------------------------------------------------------------------------------- datasets
def _ds_dir(ds_id: str) -> Path:
    return root() / "datasets" / ds_id


def _save(ds: dict[str, Any]) -> dict[str, Any]:
    (_ds_dir(ds["id"]) / "dataset.json").write_text(json.dumps(ds, ensure_ascii=False, indent=1), encoding="utf-8")
    return ds


def _new(name: str, voice_id: str) -> dict[str, Any]:
    ds = {"id": uuid.uuid4().hex[:10], "name": name.strip() or "학습 데이터", "voice_id": voice_id, "created": time.time(), "items": []}
    (_ds_dir(ds["id"]) / "clips").mkdir(parents=True)
    return ds


def _add(ds: dict[str, Any], audio: np.ndarray, text: str, source: str) -> None:
    iid = uuid.uuid4().hex[:8]
    write_wav(_ds_dir(ds["id"]) / "clips" / f"{iid}.wav", audio, SR)
    text = (text or "").strip()
    ds["items"].append({"id": iid, "file": f"clips/{iid}.wav", "text": text, "include": bool(text), "confirmed": False,
                        "duration": round(len(audio) / SR, 2), "source": source})


def from_voice(voice_id: str, name: str = "") -> dict[str, Any]:
    """A registered voice's reference clips (silence added around each) with their transcripts."""
    from . import voices
    v = voices.get_voice(voice_id)
    if not v or not v.samples:
        raise KeyError(voice_id)
    ds = _new(name or v.name, voice_id)
    for s in v.samples:
        audio, _ = read_audio(voices.sample_path(voice_id, s.id), SR)
        pad = room_tone(audio, PAD_S)
        _add(ds, np.concatenate([pad, audio, pad]), s.transcript, f"sample:{s.id}")
    return _save(ds)


def room_tone(audio: np.ndarray, seconds: float, win: float = 0.1) -> np.ndarray:
    """``seconds`` of the clip's own quietest 100 ms, repeated: digital zeros around the clips taught the model a
    silence it never produces, and it then kept "waiting" up to 2 s before stopping (2026-10-19)."""
    n, want = int(win * SR), int(seconds * SR)
    if len(audio) < 2 * n:
        return np.zeros(want, dtype=np.float32)
    k = len(audio) // n
    q = int(np.argmin(np.sqrt(np.mean(audio[: k * n].reshape(k, n) ** 2, axis=1))))
    seg = audio[q * n:(q + 1) * n].astype(np.float32)
    out = np.tile(np.concatenate([seg, seg[::-1]]), want // (2 * n) + 1)[:want].copy()   # mirrored: no clicks at the joins
    f = min(int(0.01 * SR), want // 4)
    if f > 0:
        out[:f] *= np.linspace(0, 1, f, dtype=np.float32)
        out[-f:] *= np.linspace(1, 0, f, dtype=np.float32)
    return out


def from_recordings(paths: list[Path], name: str, voice_id: str = "", transcribe: bool = True,
                    settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """Long recordings cut at pauses into 3-14 s clips (0.3 s of the real surroundings kept) with Whisper drafts."""
    from . import slicer
    settings = settings or {}
    ds = _new(name, voice_id)
    for p in paths:
        for c in slicer.process(Path(p), sr=SR, transcribe=transcribe, max_clips=0, min_len=3.0, pad=0.3,
                                model_size=settings.get("asr_model") or "small", device=settings.get("asr_device") or "auto"):
            _add(ds, c.audio, c.transcript, f"{Path(p).name}@{c.start:.1f}s")
    if not ds["items"]:
        shutil.rmtree(_ds_dir(ds["id"]), ignore_errors=True)
        raise ValueError("녹음에서 3초 넘는 말소리 구간을 찾지 못했습니다.")
    return _save(ds)


def get_dataset(ds_id: str) -> dict[str, Any] | None:
    f = _ds_dir(ds_id) / "dataset.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def summary(ds: dict[str, Any]) -> dict[str, Any]:
    used = [i for i in ds["items"] if i["include"] and i["text"]]
    return {"id": ds["id"], "name": ds["name"], "voice_id": ds.get("voice_id", ""), "created": ds["created"],
            "items": len(ds["items"]), "included": len(used), "confirmed": sum(1 for i in used if i.get("confirmed")),
            "minutes": round(sum(i["duration"] for i in used) / 60, 1)}


def list_datasets() -> list[dict[str, Any]]:
    out = [get_dataset(p.name) for p in sorted((root() / "datasets").iterdir()) if (p / "dataset.json").exists()]
    return sorted((summary(d) for d in out if d), key=lambda d: -d["created"])


def update_item(ds_id: str, item_id: str, **fields: Any) -> dict[str, Any]:
    ds = get_dataset(ds_id)
    item = next((i for i in (ds or {}).get("items", []) if i["id"] == item_id), None)
    if item is None:
        raise KeyError(item_id)
    for k in ("text", "include", "confirmed"):
        if k in fields:
            item[k] = str(fields[k]).strip() if k == "text" else bool(fields[k])
    _save(ds)
    return item


def item_path(ds_id: str, item_id: str) -> Path | None:
    ds = get_dataset(ds_id)
    item = next((i for i in (ds or {}).get("items", []) if i["id"] == item_id), None)
    return _ds_dir(ds_id) / item["file"] if item else None


def delete_dataset(ds_id: str) -> None:
    shutil.rmtree(_ds_dir(ds_id), ignore_errors=True)


# ------------------------------------------------------------------------------------------- training process
_PROC: dict[str, subprocess.Popen] = {}
_LOCK = threading.Lock()


def available() -> tuple[bool, str]:
    import importlib.util
    if importlib.util.find_spec("torch") is None or importlib.util.find_spec("qwen_tts") is None:
        return False, "목소리 복제 엔진(qwen-tts)을 설치해야 학습할 수 있습니다."
    from .tts.qwen import pick_device
    return True, {"cuda": "NVIDIA GPU", "mps": "Apple GPU", "cpu": "CPU (아주 느림)"}.get(pick_device("auto"), "")


def active() -> str | None:
    """Id of the model being trained right now, if any."""
    with _LOCK:
        for mid, p in list(_PROC.items()):
            if p.poll() is None:
                return mid
            _PROC.pop(mid)
    return None


def start(ds_id: str, name: str, base_model: str, **opts: Any) -> dict[str, Any]:
    if active():
        raise RuntimeError("이미 학습 중인 목소리가 있습니다.")
    ds = get_dataset(ds_id)
    if not ds:
        raise KeyError(ds_id)
    if summary(ds)["included"] < MIN_ITEMS:
        raise ValueError(f"전사가 있는 클립이 {MIN_ITEMS}개 이상 있어야 학습할 수 있습니다.")
    mid = uuid.uuid4().hex[:10]
    d = model_dir(mid)
    d.mkdir(parents=True)
    cfg = {"id": mid, "name": name.strip() or f"{ds['name']} (학습)", "dataset_id": ds_id, "voice_id": ds.get("voice_id", ""),
           "base": base_model, "created": time.time(), **DEFAULTS,
           **{k: type(DEFAULTS[k])(v) for k, v in opts.items() if k in DEFAULTS and v not in (None, "")}}
    (d / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    _progress(d, stage="queued", message="학습 준비 중")
    _spawn(d)
    return status(mid)


def _spawn(d: Path) -> None:
    pkg_parent = str(Path(__file__).resolve().parents[1])
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(x for x in (pkg_parent, os.environ.get("PYTHONPATH", "")) if x)}
    with open(d / "train.log", "w", encoding="utf-8") as log:
        p = subprocess.Popen([sys.executable, "-m", "nursing_tts.finetune", str(d)], stdout=log, stderr=subprocess.STDOUT, env=env,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))   # no console window on Windows
    with _LOCK:
        _PROC[d.name] = p


def cancel(model_id: str) -> dict[str, Any]:
    with _LOCK:
        p = _PROC.get(model_id)
    if p and p.poll() is None:
        p.terminate()
        try:
            p.wait(15)
        except subprocess.TimeoutExpired:
            p.kill()
        _progress(model_dir(model_id), stage="cancelled", message="학습을 취소했습니다.")
    return status(model_id)


def _progress(d: Path, **kw: Any) -> None:
    with open(d / "progress.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": round(time.time(), 1), **kw}, ensure_ascii=False) + "\n")


def status(model_id: str) -> dict[str, Any]:
    d = model_dir(model_id)
    cfg = json.loads((d / "config.json").read_text(encoding="utf-8"))
    lines = (d / "progress.jsonl").read_text(encoding="utf-8").splitlines() if (d / "progress.jsonl").exists() else []
    last = json.loads(lines[-1]) if lines else {"stage": "queued"}
    ends = [json.loads(x) for x in lines if '"epoch_end"' in x]
    losses = [[e["loss"], e.get("val_loss")] for e in ends]   # per pass: training, held-out
    with _LOCK:
        p = _PROC.get(model_id)
    running = bool(p and p.poll() is None)
    if not running and last.get("stage") not in ("done", "error", "cancelled"):
        tail = (d / "train.log").read_text(encoding="utf-8", errors="replace").strip().splitlines()[-3:] if (d / "train.log").exists() else []
        last = {**last, "stage": "error", "message": "학습 프로세스가 중간에 끝났습니다. " + " / ".join(tail)[-300:]}
    out = {**cfg, **last, "running": running, "epoch_losses": losses, "ready": last.get("stage") == "done"}
    if ends:   # while training: the latest pass; once saved: the pass that was kept
        kept = next((e for e in ends if e["epoch"] == ends[-1].get("best_epoch")), ends[-1]) if last.get("stage") == "done" else ends[-1]
        out.update(loss=kept["loss"], val_loss=kept.get("val_loss"), best_epoch=ends[-1].get("best_epoch"))
    return out


def list_models() -> list[dict[str, Any]]:
    out = [status(p.name) for p in (root() / "models").iterdir() if (p / "config.json").exists()]
    return sorted(out, key=lambda m: -m["created"])


def delete_model(model_id: str) -> None:
    cancel(model_id)
    from . import voices
    for v in voices.list_voices():
        if getattr(v, "model", "") == model_id:
            voices.delete_voice(v.id)
    shutil.rmtree(model_dir(model_id), ignore_errors=True)


# --------------------------------------------------------------------------------------------------- LoRA
_LORA_CLS = None


def _lora_cls():
    global _LORA_CLS
    if _LORA_CLS is None:
        import torch

        class LoRALinear(torch.nn.Module):
            """y = W x + B A x * alpha/r with W frozen; A, B are fp32 masters computed in the input's dtype."""

            def __init__(self, base: torch.nn.Linear, r: int, alpha: float):
                super().__init__()
                self.base, self.scale, self.enabled = base, alpha / r, True
                dev = base.weight.device
                self.A = torch.nn.Parameter(torch.empty(r, base.in_features, device=dev, dtype=torch.float32))
                self.B = torch.nn.Parameter(torch.zeros(base.out_features, r, device=dev, dtype=torch.float32))
                torch.nn.init.kaiming_uniform_(self.A, a=math.sqrt(5))

            def forward(self, x):
                y = self.base(x)
                if not self.enabled:
                    return y
                return y + (x @ self.A.t().to(x.dtype)) @ self.B.t().to(x.dtype) * self.scale

        _LORA_CLS = LoRALinear
    return _LORA_CLS


def wrap(talker, rank: int, alpha: float) -> list[str]:
    """Put adapters on the talker's (and its code predictor's) attention/MLP projections; already wrapped ones stay."""
    import torch
    cls = _lora_cls()
    names = []
    for name, mod in list(talker.named_modules()):
        for cn, child in list(mod.named_children()):
            if cn in TARGET and isinstance(child, torch.nn.Linear):
                setattr(mod, cn, cls(child, rank, alpha))
            if cn in TARGET and isinstance(getattr(mod, cn), cls):
                names.append(f"{name}.{cn}" if name else cn)
    return names


def _set_enabled(talker, on: bool) -> None:
    cls = _lora_cls()
    for mod in talker.modules():
        if isinstance(mod, cls):
            mod.enabled = on


@contextlib.contextmanager
def use(m, adapter_dir: Path):
    """Let the loaded Base model (``Qwen3TTSModel``) speak as a fine-tuned voice for the duration of the block:
    adapters on, the speaker embedding in slot 3000 and the custom-voice switches the library checks; all undone
    after, so zero-shot cloning with the same weights is unaffected."""
    import torch
    model = m.model
    talker, tc = model.talker, model.config.talker_config
    emb = talker.model.codec_embedding.weight
    if getattr(model, "_nt_adapter", None) != str(adapter_dir):
        ad = torch.load(Path(adapter_dir) / "adapter.pt", map_location="cpu")
        wrap(talker, int(ad["rank"]), float(ad["alpha"]))
        mods = dict(talker.named_modules())
        for name, (a, b) in ad["lora"].items():   # model dtype at inference: no per-step casts in the code predictor loop
            mods[name].A = torch.nn.Parameter(a.to(emb.device, emb.dtype), requires_grad=False)
            mods[name].B = torch.nn.Parameter(b.to(emb.device, emb.dtype), requires_grad=False)
            mods[name].scale = float(ad["alpha"]) / int(ad["rank"])
        model._nt_spk = ad["spk"].to(emb.device, emb.dtype)
        model._nt_adapter = str(adapter_dir)
    saved = (model.config.tts_model_type, model.tts_model_type, tc.spk_id, tc.spk_is_dialect, model.supported_speakers,
             emb[SPK_ID].detach().clone())
    try:
        _set_enabled(talker, True)
        with torch.no_grad():
            emb[SPK_ID] = model._nt_spk
        model.config.tts_model_type = model.tts_model_type = "custom_voice"
        tc.spk_id, tc.spk_is_dialect = {SPEAKER: SPK_ID}, {SPEAKER: False}
        model.supported_speakers = tc.spk_id.keys()        # the library keeps a keys() view of the dict it started with
        yield
    finally:
        _set_enabled(talker, False)
        with torch.no_grad():
            emb[SPK_ID] = saved[5]
        model.config.tts_model_type, model.tts_model_type, tc.spk_id, tc.spk_is_dialect, model.supported_speakers = saved[:5]


# --------------------------------------------------------------------------------------------- the child process
def _collate(batch: list[dict[str, Any]], cfg) -> tuple:
    """Official finetuning/dataset.py collate_fn: text first, then the target codes (non-streaming layout)."""
    import torch
    tc = cfg.talker_config
    L = max(b["tids"].shape[1] + b["codes"].shape[0] for b in batch) + 8
    B = len(batch)
    input_ids = torch.zeros((B, L, 2), dtype=torch.long)
    codec_ids = torch.zeros((B, L, 16), dtype=torch.long)
    tmask = torch.zeros((B, L), dtype=torch.bool)
    cmask_e = torch.zeros((B, L), dtype=torch.bool)
    cmask = torch.zeros((B, L), dtype=torch.bool)
    att = torch.zeros((B, L), dtype=torch.long)
    lab = torch.full((B, L), -100, dtype=torch.long)
    for i, d in enumerate(batch):
        t, c = d["tids"], d["codes"]
        tl, cl = t.shape[1], c.shape[0]
        input_ids[i, :3, 0] = t[0, :3]
        input_ids[i, 3:7, 0] = cfg.tts_pad_token_id
        input_ids[i, 7, 0] = cfg.tts_bos_token_id
        input_ids[i, 8:8 + tl - 3, 0] = t[0, 3:]
        input_ids[i, 8 + tl - 3, 0] = cfg.tts_eos_token_id
        input_ids[i, 8 + tl - 2:8 + tl + cl, 0] = cfg.tts_pad_token_id
        tmask[i, :8 + tl + cl] = True
        input_ids[i, 3:8, 1] = torch.tensor([tc.codec_nothink_id, tc.codec_think_bos_id, tc.codec_think_eos_id, 0, tc.codec_pad_id])
        input_ids[i, 8:8 + tl - 2, 1] = tc.codec_pad_id
        input_ids[i, 8 + tl - 2, 1] = tc.codec_bos_id
        input_ids[i, 8 + tl - 1:8 + tl - 1 + cl, 1] = c[:, 0]
        input_ids[i, 8 + tl - 1 + cl, 1] = tc.codec_eos_token_id
        lab[i, 8 + tl - 1:8 + tl - 1 + cl] = c[:, 0]
        lab[i, 8 + tl - 1 + cl] = tc.codec_eos_token_id
        codec_ids[i, 8 + tl - 1:8 + tl - 1 + cl, :] = c
        cmask_e[i, 3:8 + tl + cl] = True
        cmask_e[i, 6] = False                       # the speaker embedding goes here
        cmask[i, 8 + tl - 1:8 + tl - 1 + cl] = True
        att[i, :8 + tl + cl] = 1
    return input_ids, codec_ids, tmask.unsqueeze(-1), cmask_e.unsqueeze(-1), cmask, att, lab


def _loss(model, batch: tuple, spk, dev: str):
    """Teacher-forced loss in the layout of the official recipe, aligned the way generation runs.

    The official sft_12hz.py does not hold with this library (transformers 4.57, checked 2026-10-19 on the base
    model): it feeds text embeddings without ``text_projection`` (inference always projects; base-model loss 8.5
    instead of 1.6), pre-shifts labels that ``ForCausalLMLoss`` shifts again (frame k+2 instead of k+1), and pairs
    the code predictor with the hidden state of the frame itself instead of the one that predicted it. A model trained
    that way babbled for the whole 72-second ceiling. Here the step that reads frame k-1 predicts frame k's first
    codebook (and the last frame predicts EOS), and its hidden state seeds the code predictor for frame k, as in
    ``Qwen3TTSTalkerForConditionalGeneration.forward`` during generation."""
    import torch
    import torch.nn.functional as F
    talker = model.talker
    input_ids, codec_ids, tmask, cmask_e, cmask, att, lab = [x.to(dev) for x in batch]
    emb = talker.text_projection(talker.model.text_embedding(input_ids[:, :, 0])) * tmask
    ce = talker.model.codec_embedding(input_ids[:, :, 1]) * cmask_e
    ce[:, 6, :] = spk.to(ce.dtype)
    emb = emb + ce
    for i in range(1, 16):
        emb = emb + talker.code_predictor.get_input_embeddings()[i - 1](codec_ids[:, :, i]) * cmask.unsqueeze(-1)
    out = talker(inputs_embeds=emb, attention_mask=att, output_hidden_states=True)
    b, pos = torch.nonzero(cmask, as_tuple=True)              # frame k sits at pos; the step at pos - 1 predicts it
    rows = torch.arange(cmask.shape[0], device=cmask.device)
    end = cmask.float().argmax(1).long() + cmask.sum(1) - 1   # the last frame's step predicts EOS (label at end + 1)
    t_loss = F.cross_entropy(torch.cat([out.logits[b, pos - 1], out.logits[rows, end]]).float(),
                             torch.cat([lab[b, pos], lab[rows, end + 1]]))
    codes = codec_ids[b, pos]                                  # (frames, 16)
    sub_in = [out.hidden_states[0][-1][b, pos - 1].unsqueeze(1), talker.get_input_embeddings()(codes[:, :1])]
    sub_in += [talker.code_predictor.get_input_embeddings()[i - 1](codes[:, i:i + 1]) for i in range(1, 15)]
    sub = talker.code_predictor.forward_finetune(inputs_embeds=torch.cat(sub_in, dim=1), labels=None)
    s_loss = F.cross_entropy(sub.logits.float().reshape(-1, sub.logits.shape[-1]), codes[:, 1:].reshape(-1))
    return t_loss + 0.3 * s_loss


def _train(d: Path, cfg: dict[str, Any]) -> None:
    import torch
    from qwen_tts import Qwen3TTSModel
    from qwen_tts.core.models.modeling_qwen3_tts import mel_spectrogram

    from .korean import to_tts_text
    from .tts.qwen import pick_device

    dev = pick_device("auto")
    _progress(d, stage="load", message="기본 모델을 불러오는 중")
    m = Qwen3TTSModel.from_pretrained(cfg["base"], device_map=dev, dtype=torch.float32 if dev == "cpu" else torch.bfloat16)
    model = m.model
    ds = get_dataset(cfg["dataset_id"])
    items = []
    for it in ds["items"]:
        if it["include"] and it["text"]:
            audio, _ = read_audio(_ds_dir(ds["id"]) / it["file"], SR)
            items.append({"audio": audio.astype(np.float32), "text": to_tts_text(it["text"], random.Random(0)), "dur": it["duration"]})
    _progress(d, stage="encode", message=f"클립 {len(items)}개를 음성 코드로 바꾸는 중")
    with torch.no_grad():
        for k in range(0, len(items), 8):
            enc = model.speech_tokenizer.encode([it["audio"] for it in items[k:k + 8]], sr=SR)
            for it, c in zip(items[k:k + 8], enc.audio_codes):
                it["codes"] = c.cpu().long()

    def mel(a):
        return mel_spectrogram(torch.from_numpy(a).unsqueeze(0), n_fft=1024, num_mels=128, sampling_rate=SR, hop_size=256,
                               win_size=1024, fmin=0, fmax=12000).transpose(1, 2)
    ref = min(items, key=lambda it: abs(it["dur"] - 10.0))       # official: one reference clip for every sample
    with torch.no_grad():
        spk = model.speaker_encoder(mel(ref["audio"]).to(dev).to(model.dtype)).detach()
    for it in items:
        ids = m.processor(text=f"<|im_start|>assistant\n{it['text']}<|im_end|>\n<|im_start|>assistant\n",
                          return_tensors="pt", padding=True)["input_ids"]
        it["tids"] = (ids.unsqueeze(0) if ids.dim() == 1 else ids)[:, :-5]

    for p in model.parameters():
        p.requires_grad_(False)
    rank, alpha = int(cfg["rank"]), 2.0 * int(cfg["rank"])
    names = wrap(model.talker, rank, alpha)
    params = [p for n, p in model.talker.named_parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=float(cfg["lr"]), weight_decay=0.0)
    for sub in (model.talker.model, model.talker.code_predictor.model):
        sub.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    codec = getattr(model.speech_tokenizer, "model", None)
    if codec is not None:
        codec.to("cpu")                  # not needed again until the next synthesis; frees ~1 GB on the GPU
    if dev == "mps":
        torch.mps.empty_cache()
    elif dev == "cuda":
        torch.cuda.empty_cache()

    loss_of = lambda batch: _loss(model, batch, spk, dev)   # noqa: E731

    epochs, accum = int(cfg["epochs"]), int(cfg["accum"])
    random.Random(0).shuffle(items)
    n_val = max(2, len(items) // 10) if len(items) >= 10 else 0
    val, items = items[:n_val], items[n_val:]          # held out: 6 minutes over-fit by the 8th pass (2026-10-19)
    total, done, t0, last_note = epochs * len(items), 0, time.time(), 0.0
    best, best_ep, best_state = float("inf"), 0, None
    model.train()
    for ep in range(epochs):
        random.Random(ep).shuffle(items)
        losses = []
        for k, it in enumerate(items):
            loss = loss_of(_collate([it], model.config))
            (loss / accum).backward()
            losses.append(float(loss.detach()))
            if (k + 1) % accum == 0 or k + 1 == len(items):
                torch.nn.utils.clip_grad_norm_(params, 1.0)
                opt.step()
                opt.zero_grad()
            done += 1
            if time.time() - last_note > 5:
                el = time.time() - t0
                _progress(d, stage="train", epoch=ep + 1, epochs=epochs, step=done, steps=total,
                          loss=round(float(np.mean(losses)), 3), eta_s=int(el / done * (total - done)),
                          message=f"{ep + 1}/{epochs}번째 학습 중")
                last_note = time.time()
        vloss = None
        if val:
            model.eval()
            with torch.no_grad():
                vloss = float(np.mean([float(loss_of(_collate([it], model.config))) for it in val]))
            model.train()
        if vloss is None or vloss < best:      # keep the pass that reads unseen clips best, not the last one
            best, best_ep = (vloss if vloss is not None else best), ep + 1
            best_state = {n: (model.talker.get_submodule(n).A.detach().cpu().clone(), model.talker.get_submodule(n).B.detach().cpu().clone())
                          for n in names}
        _progress(d, stage="train", event="epoch_end", epoch=ep + 1, epochs=epochs, step=done, steps=total,
                  loss=round(float(np.mean(losses)), 3), val_loss=None if vloss is None else round(vloss, 3), best_epoch=best_ep,
                  eta_s=int((time.time() - t0) / done * (total - done)))

    _progress(d, stage="save", message="학습 결과 저장 중")
    torch.save({"lora": best_state, "spk": spk[0].detach().float().cpu(), "rank": rank, "alpha": alpha, "base": cfg["base"],
                "epoch": best_ep}, d / "adapter.pt")
    _register_voice(d, cfg, f"목소리 학습 모델 · 클립 {len(items) + len(val)}개 · {best_ep}/{epochs}회째 결과", best_epoch=best_ep,
                    minutes=round((time.time() - t0) / 60, 1))


def _register_voice(d: Path, cfg: dict[str, Any], note: str, **extra: Any) -> str:
    """The finished adapter becomes a voice of its own (same sex as the source voice), picked like any other."""
    from . import voices
    src = voices.get_voice(cfg.get("voice_id") or "")
    v = voices.create_voice(cfg["name"], note=note, sex=src.sex if src else "")
    v.model = d.name
    voices._save(v)
    cfg["voice"] = v.id
    (d / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    _progress(d, stage="done", message="학습이 끝났습니다. 목소리 목록에 추가했습니다.", voice=v.id, **extra)
    return v.id


def train_main(d: Path) -> None:
    cfg = json.loads((d / "config.json").read_text(encoding="utf-8"))
    try:
        _train(d, cfg)
    except Exception as e:  # noqa: BLE001
        _progress(d, stage="error", message=f"{type(e).__name__}: {e}"[:400])
        raise


if __name__ == "__main__":
    train_main(Path(sys.argv[1]))
