"""Operating-system TTS (macOS `say`, Windows SAPI, Linux espeak-ng).

Not a voice-cloning engine - this is a stand-in for checking the pipeline when
no cloning model is installed.  The voice clearly differs from a registered
nurse voice; the UI labels it as such.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from ..audio.io import read_audio


class SystemTTSEngine:
    key = "system"
    label = "시스템 TTS (테스트용, 목소리 복제 아님)"
    clones_voice = False

    def __init__(self, sr: int = 24000):
        self.sr = sr
        self.system = platform.system()

    def available(self) -> tuple[bool, str]:
        if self.system == "Darwin":
            return (shutil.which("say") is not None), "macOS say"
        if self.system == "Windows":
            return (shutil.which("powershell") is not None), "Windows SAPI (System.Speech)"
        return (shutil.which("espeak-ng") is not None or shutil.which("espeak") is not None), "espeak-ng"

    def synthesize(self, text: str, ref: tuple[Path, str] | None, seed: int | None = None) -> tuple[np.ndarray, int]:
        with tempfile.TemporaryDirectory() as td:
            td_p = Path(td)
            txt = td_p / "in.txt"
            txt.write_text(text, encoding="utf-8")
            if self.system == "Darwin":
                out = td_p / "out.aiff"
                # Prefer a Korean voice if installed (Yuna); fall back to default.
                voice = []
                try:
                    voices = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
                    if "Yuna" in voices:
                        voice = ["-v", "Yuna"]
                except Exception:
                    pass
                subprocess.run(["say", *voice, "-f", str(txt), "-o", str(out)], check=True)
            elif self.system == "Windows":
                out = td_p / "out.wav"
                ps = (
                    "Add-Type -AssemblyName System.Speech; "
                    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    "$v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'ko*' } | Select-Object -First 1; "
                    "if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }; "
                    f"$t = Get-Content -Raw -Encoding UTF8 '{txt}'; "
                    f"$s.SetOutputToWaveFile('{out}'); $s.Speak($t); $s.Dispose()"
                )
                subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
            else:
                out = td_p / "out.wav"
                exe = shutil.which("espeak-ng") or shutil.which("espeak")
                subprocess.run([exe, "-v", "ko", "-s", "150", "-f", str(txt), "-w", str(out)], check=True)
            audio, sr = read_audio(out, self.sr)
            return audio, sr
