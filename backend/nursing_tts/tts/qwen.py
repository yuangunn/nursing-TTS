"""Qwen3-TTS adapter: built-in zero-shot voice cloning with official Korean support (Apache-2.0).

Install with ``pip install -r requirements-qwen.txt``.  The model (default
``Qwen/Qwen3-TTS-12Hz-1.7B-Base``) is fetched from Hugging Face by the app
installer or on first use.
"""
from __future__ import annotations

import importlib.util
import threading
import time
from pathlib import Path

import numpy as np

from ..audio.io import read_audio, resample


def pick_device(pref: str) -> str:
    if pref and pref != "auto":
        return pref
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except Exception:  # noqa: BLE001
        pass
    return "cpu"


def model_cached(model_id: str) -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache
        return isinstance(try_to_load_from_cache(model_id, "config.json"), str)
    except Exception:  # noqa: BLE001
        return False


_PROMPT_CACHE = 6   # reference prompts kept on the device at once


class QwenEngine:
    key = "qwen"
    label = "Qwen3-TTS (내장 한국어 목소리 복제)"
    clones_voice = True

    def __init__(self, model: str = "Qwen/Qwen3-TTS-12Hz-1.7B-Base", device: str = "auto", sr: int = 24000,
                 idle_unload_min: float = 10, batch: int = 8):
        self.model = model
        self.device_pref = device
        self.sr = sr
        self.batch = max(1, int(batch or 1))  # sentence chunks per generate call (decode is memory-bound, so batching is ~free)
        self.idle_unload_s = float(idle_unload_min or 0) * 60
        self._m = None
        self._prompts: dict[tuple, object] = {}  # reference prompts on the device; capped at _PROMPT_CACHE (2026-10-17: 35 samples of one voice ate memory)
        self._lock = threading.Lock()
        self._last_used = 0.0

    def available(self) -> tuple[bool, str]:
        if importlib.util.find_spec("qwen_tts") is None:
            return False, "qwen-tts 미설치 (마법사 또는 설정 탭에서 '목소리 복제 엔진' 설치)"
        note = "모델 캐시됨" if model_cached(self.model) else "첫 합성 전에 모델을 내려받습니다 (수 GB)"
        return True, f"device={pick_device(self.device_pref)} · {self.model} · {note}"

    # -- model lifecycle: the weights hold several GB of unified/GPU memory, so drop them after idling -------------
    def _load(self):
        if self._m is None:
            import torch
            from qwen_tts import Qwen3TTSModel
            dev = pick_device(self.device_pref)
            dtype = torch.float32 if dev == "cpu" else torch.bfloat16
            self._m = Qwen3TTSModel.from_pretrained(self.model, device_map=dev, dtype=dtype)
            self._prompts.clear()
            if self.idle_unload_s > 0:
                self._arm_timer()
        return self._m

    def _arm_timer(self) -> None:
        t = threading.Timer(self.idle_unload_s, self._maybe_unload)
        t.daemon = True
        t.start()

    def _maybe_unload(self) -> None:
        with self._lock:
            if self._m is None:
                return
            if time.time() - self._last_used < self.idle_unload_s:
                self._arm_timer()
                return
            self._m = None
            self._prompts.clear()
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            elif hasattr(torch, "mps"):
                torch.mps.empty_cache()
        except Exception:  # noqa: BLE001
            pass

    def synthesize(self, text: str, ref: tuple[Path, str] | None, seed: int | None = None) -> tuple[np.ndarray, int]:
        wavs, sr = self.synthesize_many([text], ref, seed)
        return wavs[0], sr

    def synthesize_many(self, texts: list[str], ref: tuple[Path, str] | None,
                        seed: int | None = None) -> tuple[list[np.ndarray], int]:
        """Batched generation: ``self.batch`` texts per call share one voice prompt."""
        if ref is None:
            raise RuntimeError("Qwen3-TTS는 참조 음성(등록된 목소리)이 필요합니다.")
        ref_path, ref_text = ref
        out: list[np.ndarray] = []
        with self._lock:
            m = self._load()
            key = (str(ref_path), ref_path.stat().st_mtime, ref_text)
            prompt = self._prompts.get(key)
            if prompt is None:  # encode the reference once per sample; batches reuse it
                audio, sr = read_audio(ref_path)
                prompt = m.create_voice_clone_prompt(ref_audio=(audio, sr), ref_text=ref_text or None,
                                                     x_vector_only_mode=not ref_text)
                self._prompts[key] = prompt
                while len(self._prompts) > _PROMPT_CACHE:          # oldest first (dict keeps insertion order)
                    self._prompts.pop(next(iter(self._prompts)))
            for start in range(0, len(texts), self.batch):
                group = texts[start:start + self.batch]
                if seed is not None:
                    import torch
                    torch.manual_seed(seed + start)
                wavs, sr = m.generate_voice_clone(text=group, language="Korean", voice_clone_prompt=prompt)
                out.extend(np.asarray(w, dtype=np.float32) for w in wavs)
            self._last_used = time.time()
        fixed: list[np.ndarray] = []
        for audio in out:
            if audio.ndim > 1:
                audio = audio.mean(axis=-1)
            if sr != self.sr:
                audio = resample(audio, sr, self.sr)
            fixed.append(audio)
        return fixed, self.sr
