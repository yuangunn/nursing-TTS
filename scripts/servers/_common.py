"""Shared FastAPI shell for the wrapper servers (same contract as example_tts_server.py)."""
from __future__ import annotations

import io
import tempfile
from pathlib import Path
from typing import Callable

import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import Response

Synth = Callable[[str, Path | None, str, int | None], tuple[np.ndarray, int]]


def make_app(synthesize: Synth, name: str) -> FastAPI:
    app = FastAPI(title=name)

    @app.get("/health")
    def health():
        return {"ok": True, "engine": name}

    @app.post("/synthesize")
    async def synth(text: str = Form(...), ref_text: str = Form(""), seed: str = Form(""),
                    ref_audio: UploadFile | None = File(None)):
        ref_path = None
        if ref_audio is not None:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                tmp.write(await ref_audio.read())
                ref_path = Path(tmp.name)
        try:
            audio, sr = synthesize(text, ref_path, ref_text, int(seed) if seed else None)
        finally:
            if ref_path:
                ref_path.unlink(missing_ok=True)
        audio = np.asarray(audio, dtype=np.float32)
        if audio.ndim > 1:
            audio = audio.reshape(-1) if min(audio.shape) == 1 else audio.mean(axis=0 if audio.shape[0] < audio.shape[1] else 1)
        buf = io.BytesIO()
        sf.write(buf, np.clip(audio, -1, 1), sr, format="WAV", subtype="PCM_16")
        return Response(content=buf.getvalue(), media_type="audio/wav")

    return app


def run(app: FastAPI, default_port: int) -> None:
    import argparse

    import uvicorn

    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=default_port)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
