"""Loads faster-whisper and transcribes numpy audio arrays."""
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

from .config import Config

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


def _resolve_model_path(model_size: str) -> str:
    """Use the vendored local model if we shipped one, else fall back to the
    Hugging Face repo id (faster-whisper downloads + caches it on first use)."""
    local_dir = MODELS_DIR / model_size
    if (local_dir / "model.bin").exists():
        return str(local_dir)
    return model_size


def _resolve_device_and_compute_type(cfg: Config) -> tuple[str, str]:
    if cfg.device != "auto":
        device = cfg.device
    else:
        try:
            import ctranslate2

            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            device = "cpu"

    if cfg.compute_type != "auto":
        compute_type = cfg.compute_type
    else:
        compute_type = "float16" if device == "cuda" else "int8"

    return device, compute_type


class Transcriber:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        device, compute_type = _resolve_device_and_compute_type(cfg)
        model_path = _resolve_model_path(cfg.model_size)
        print(f"Loading Whisper model '{model_path}' on {device} ({compute_type})...")
        self.model = WhisperModel(model_path, device=device, compute_type=compute_type)
        print("Model loaded.")

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""
        language = None if self.cfg.language == "auto" else self.cfg.language
        segments, _info = self.model.transcribe(
            audio,
            language=language,
            vad_filter=True,
        )
        return "".join(segment.text for segment in segments).strip()
