"""Recording catalogue, QA review flags and dataset export (manifests + splits)."""
from __future__ import annotations

import csv
import json
import random
import shutil
import time
from pathlib import Path
from typing import Any

import numpy as np

from .audio.io import read_audio, write_wav
from .config import output_dir


def _json_for(wav: Path) -> Path:
    return wav.with_suffix(".json")


def list_recordings(limit: int = 2000) -> list[dict[str, Any]]:
    folder = output_dir()
    wavs = sorted(folder.rglob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    out = []
    for p in wavs:
        rel = str(p.relative_to(folder)).replace("\\", "/")
        item: dict[str, Any] = {"rel": rel, "name": p.name, "size": p.stat().st_size, "mtime": p.stat().st_mtime}
        jp = _json_for(p)
        if jp.exists():
            try:
                meta = json.loads(jp.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                meta = {}
            item.update({
                "template": meta.get("template"), "record_kind": meta.get("record_kind"),
                "patient": (meta.get("patient") or {}).get("name"), "voice_id": meta.get("voice_id"),
                "voice_name": meta.get("voice_name"), "engine": meta.get("engine"),
                "duration": meta.get("duration_sec"), "noise": (meta.get("noise") or {}).get("enabled"),
                "channel": (meta.get("augment") or {}).get("channel"), "disfluency": meta.get("disfluency_level", 0),
                "review": (meta.get("review") or {}).get("status", "pending"),
                "review_note": (meta.get("review") or {}).get("note", ""),
                "verify": meta.get("verify"), "signal": meta.get("signal"), "spoken_text": meta.get("spoken_text"),
                "verbatim_text": meta.get("verbatim_text"), "signal_format": meta.get("signal_format"),
                "signal_parse": meta.get("signal_parse"), "datetime": meta.get("datetime"),
            })
        out.append(item)
    return out


def _resolve(rel: str) -> Path:
    folder = output_dir().resolve()
    p = (folder / rel).resolve()
    if folder not in p.parents or p.suffix != ".wav" or not p.exists():
        raise FileNotFoundError(rel)
    return p


def set_review(rel: str, status: str, note: str = "") -> dict[str, Any]:
    p = _resolve(rel)
    jp = _json_for(p)
    meta = json.loads(jp.read_text(encoding="utf-8")) if jp.exists() else {}
    meta["review"] = {"status": status, "note": note, "at": time.time()}
    jp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta["review"]


def delete_recording(rel: str) -> None:
    p = _resolve(rel)
    for q in (p, p.with_suffix(".txt"), p.with_suffix(".json")):
        q.unlink(missing_ok=True)


def load_meta(rel: str) -> dict[str, Any]:
    p = _resolve(rel)
    jp = _json_for(p)
    return json.loads(jp.read_text(encoding="utf-8")) if jp.exists() else {}


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export(opts: dict[str, Any]) -> dict[str, Any]:
    """opts: name, formats[ljspeech,nemo,whisper,csv], split{train,val,test}, sample_rate, include_fillers,
    only_approved, exclude_rejected, exclude_failed_verify, seed, text_field(spoken|verbatim)."""
    src = output_dir()
    name = opts.get("name") or f"dataset_{time.strftime('%Y%m%d_%H%M%S')}"
    dest = src / "_exports" / name
    wav_dir = dest / "wavs"
    wav_dir.mkdir(parents=True, exist_ok=True)
    sr = int(opts.get("sample_rate") or 16000)
    formats = set(opts.get("formats") or ["ljspeech", "nemo", "whisper"])
    split = opts.get("split") or {"train": 0.9, "val": 0.05, "test": 0.05}
    rng = random.Random(opts.get("seed", 42))
    include_fillers = bool(opts.get("include_fillers", False))

    rows: list[dict[str, Any]] = []
    skipped = {"rejected": 0, "not_approved": 0, "failed_verify": 0, "no_meta": 0}
    for rec in list_recordings(limit=100000):
        if rec["rel"].startswith("_exports/"):
            continue
        if rec.get("template") is None:
            skipped["no_meta"] += 1
            continue
        if opts.get("only_approved") and rec.get("review") != "approved":
            skipped["not_approved"] += 1
            continue
        if opts.get("exclude_rejected", True) and rec.get("review") == "rejected":
            skipped["rejected"] += 1
            continue
        v = rec.get("verify") or {}
        if opts.get("exclude_failed_verify", True) and v.get("passed") is False:
            skipped["failed_verify"] += 1
            continue
        text = (rec.get("verbatim_text") if include_fillers and rec.get("verbatim_text") else rec.get("spoken_text")) or ""
        text = " ".join(text.split())
        rows.append({**rec, "text": text})

    # speaker-stratified deterministic split
    by_speaker: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_speaker.setdefault(r.get("voice_id") or "unknown", []).append(r)
    assigned: list[tuple[str, dict[str, Any]]] = []
    for spk, items in by_speaker.items():
        rng.shuffle(items)
        n = len(items)
        n_val = int(round(n * float(split.get("val", 0.05))))
        n_test = int(round(n * float(split.get("test", 0.05))))
        for i, it in enumerate(items):
            part = "test" if i < n_test else "val" if i < n_test + n_val else "train"
            assigned.append((part, it))

    manifests = {"train": [], "val": [], "test": []}
    for part, r in assigned:
        src_wav = src / r["rel"]
        out_name = Path(r["rel"]).stem + ".wav"
        if (wav_dir / out_name).exists():
            out_name = Path(r["rel"]).parent.name + "_" + out_name
        dst = wav_dir / out_name
        audio, _ = read_audio(src_wav, sr)
        write_wav(dst, audio, sr)
        dur = round(len(audio) / sr, 3)
        sp = r.get("signal_parse") or {}
        sig_text = r.get("signal") or ""
        manifests[part].append({
            "id": dst.stem, "file": f"wavs/{out_name}", "text": r["text"], "duration": dur,
            "speaker": r.get("voice_id") or "unknown", "speaker_name": r.get("voice_name") or "",
            "record_kind": r.get("record_kind"), "template": r.get("template"), "noise": bool(r.get("noise")),
            "channel": r.get("channel"), "cer": (r.get("verify") or {}).get("cer_best"),
            # trigger labels: the signal sentence, its char span in `text`, and its parsed fields
            "signal_text": sig_text, "signal_end_char": len(sig_text) if sig_text and r["text"].startswith(sig_text) else (sp.get("end") or 0),
            "signal_format": r.get("signal_format"), "patient_name": sp.get("name") or r.get("patient"),
            "signal_datetime": sp.get("datetime") or r.get("datetime"), "signal_kind": sp.get("kind") or r.get("record_kind"),
        })

    written: list[str] = []
    all_rows = [m for part in ("train", "val", "test") for m in manifests[part]]
    if "ljspeech" in formats:
        for part in ("train", "val", "test"):
            if not manifests[part]:
                continue
            p = dest / f"metadata_{part}.csv"
            with p.open("w", encoding="utf-8", newline="") as f:
                for m in manifests[part]:
                    f.write(f"{m['id']}|{m['text']}|{m['text']}\n")
            written.append(p.name)
        p = dest / "metadata.csv"
        with p.open("w", encoding="utf-8", newline="") as f:
            for m in all_rows:
                f.write(f"{m['id']}|{m['text']}|{m['text']}\n")
        written.append(p.name)
    if "nemo" in formats:
        for part in ("train", "val", "test"):
            if not manifests[part]:
                continue
            p = dest / f"manifest_{part}.jsonl"
            with p.open("w", encoding="utf-8") as f:
                for m in manifests[part]:
                    f.write(json.dumps({"audio_filepath": m["file"], "duration": m["duration"], "text": m["text"],
                                        "speaker": m["speaker"], "signal_text": m["signal_text"], "signal_end_char": m["signal_end_char"],
                                        "signal_format": m["signal_format"], "patient_name": m["patient_name"],
                                        "signal_datetime": m["signal_datetime"], "signal_kind": m["signal_kind"]}, ensure_ascii=False) + "\n")
            written.append(p.name)
    if "whisper" in formats:
        for part in ("train", "val", "test"):
            if not manifests[part]:
                continue
            p = dest / f"whisper_{part}.jsonl"
            with p.open("w", encoding="utf-8") as f:
                for m in manifests[part]:
                    f.write(json.dumps({"audio": m["file"], "sentence": m["text"], "language": "ko",
                                        "speaker_id": m["speaker"]}, ensure_ascii=False) + "\n")
            written.append(p.name)
    if "csv" in formats:
        p = dest / "dataset.csv"
        with p.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["id", "file", "split", "text", "duration", "speaker", "speaker_name",
                                              "record_kind", "template", "noise", "channel", "cer", "signal_text",
                                              "signal_end_char", "signal_format", "patient_name", "signal_datetime", "signal_kind"])
            w.writeheader()
            for part in ("train", "val", "test"):
                for m in manifests[part]:
                    w.writerow({**m, "split": part})
        written.append(p.name)

    speakers = {}
    for m in all_rows:
        s = speakers.setdefault(m["speaker"], {"name": m["speaker_name"], "count": 0, "duration": 0.0})
        s["count"] += 1
        s["duration"] = round(s["duration"] + m["duration"], 2)
    report = {
        "name": name, "created": time.time(), "sample_rate": sr, "include_fillers": include_fillers,
        "counts": {k: len(v) for k, v in manifests.items()}, "total": len(all_rows),
        "total_duration_sec": round(sum(m["duration"] for m in all_rows), 2),
        "skipped": skipped, "speakers": speakers, "files": written, "folder": str(dest),
        "by_record_kind": {k: sum(1 for m in all_rows if m["record_kind"] == k)
                           for k in sorted({m["record_kind"] for m in all_rows if m["record_kind"]})},
    }
    (dest / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (dest / "README.md").write_text(_dataset_card(report), encoding="utf-8")
    return report


def _dataset_card(r: dict[str, Any]) -> str:
    lines = [f"# {r['name']}", "", "간호기록 음성 녹음 생성기로 만든 합성 음성 데이터셋.", "",
             f"- 클립 수: {r['total']} (train {r['counts']['train']} / val {r['counts']['val']} / test {r['counts']['test']})",
             f"- 총 길이: {r['total_duration_sec'] / 60:.1f} 분", f"- 샘플레이트: {r['sample_rate']} Hz, mono, 16-bit PCM",
             f"- 전사에 추임새 포함: {'예' if r['include_fillers'] else '아니오'}", "",
             "## 파일", "", *[f"- `{f}`" for f in r["files"]], "",
             "## 화자", "", *[f"- {k}: {v['name'] or ''} · {v['count']}개 · {v['duration'] / 60:.1f}분" for k, v in r["speakers"].items()], "",
             "## 기록 종류", "", *[f"- {k}: {v}" for k, v in r["by_record_kind"].items()], "",
             "형식: `metadata*.csv` (LJSpeech `id|text|text`), `manifest_*.jsonl` (NeMo + 시그널 라벨: signal_text / signal_end_char / signal_format / patient_name / signal_datetime / signal_kind), `whisper_*.jsonl` (HF Whisper 파인튜닝), `dataset.csv`."]
    return "\n".join(lines) + "\n"
