"""Reference implementation of the custom HTTP TTS contract used by the app.

Run:  python scripts/example_tts_server.py --port 8081
Then set 설정 → 커스텀 HTTP TTS 서버 URL to http://127.0.0.1:8081/synthesize

Replace ``synthesize()`` with calls into the voice-cloning model of your
choice (Fish Speech / OpenAudio, CosyVoice 2, XTTS v2, GPT-SoVITS, ...).  The
app sends the phonetic Korean text, a reference wav and its transcript, and
expects a WAV body back.
"""
from __future__ import annotations

import argparse
import io
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import Response

app = FastAPI()


def synthesize(text: str, ref_audio: Path | None, ref_text: str, seed: int | None) -> tuple[np.ndarray, int]:
    """Return (mono float32 audio, sample_rate).  Demo: a tone sized like speech."""
    sr = 24000
    syllables = sum(1 for ch in text if "가" <= ch <= "힣")
    n = int(max(0.5, syllables * 0.17) * sr)
    t = np.arange(n) / sr
    return (0.1 * np.sin(2 * np.pi * 240 * t)).astype(np.float32), sr


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/synthesize")
async def synth(text: str = Form(...), ref_text: str = Form(""), seed: str = Form(""),
                ref_audio: UploadFile | None = File(None)):
    ref_path = None
    if ref_audio is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(await ref_audio.read())
            ref_path = Path(tmp.name)
    audio, sr = synthesize(text, ref_path, ref_text, int(seed) if seed else None)
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
    return Response(content=buf.getvalue(), media_type="audio/wav")


if __name__ == "__main__":
    import uvicorn

    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8081)
    args = ap.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=args.port)
