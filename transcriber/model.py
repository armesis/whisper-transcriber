"""Loads faster-whisper and transcribes numpy audio arrays."""
import importlib.util
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

from .config import Config
from .paths import data_dir, resource_dir


def _model_dirs() -> list[Path]:
    """Where a ready-to-use CTranslate2 model may live, in priority order:
    vendored inside the app bundle first, then whatever we downloaded before."""
    dirs = [resource_dir() / "models"]
    downloaded = data_dir() / "models"
    if downloaded not in dirs:
        dirs.append(downloaded)
    return dirs


def _resolve_model_path(model_size: str) -> str:
    """Return a local model directory if we have one, else the Hugging Face
    repo id (faster-whisper downloads + caches it under the data directory)."""
    candidate = Path(model_size).expanduser()
    if (candidate / "model.bin").exists():
        return str(candidate)
    for base in _model_dirs():
        local_dir = base / model_size
        if (local_dir / "model.bin").exists():
            return str(local_dir)
    return model_size


def have_local_model(model_size: str) -> bool:
    """True when a model is already on disk, i.e. nothing has to be downloaded."""
    return _resolve_model_path(model_size) != model_size


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


def _vad_available() -> bool:
    """The Silero VAD runs on onnxruntime, which the smallest builds leave out
    (it is ~45 MB of the payload). Fall back quietly rather than crashing."""
    return importlib.util.find_spec("onnxruntime") is not None


def _trim_silence(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """Cheap stand-in for the VAD: drop the quiet head and tail of the clip.

    Whisper is prone to inventing text ("Thank you.", "Bye!") when handed a
    stretch of near-silence, which is exactly what the start and end of a
    push-to-talk recording look like. Cutting it costs nothing and removes most
    of the hallucinations the VAD filter was there to prevent.
    """
    frame = max(1, int(sample_rate * 0.03))
    frames = audio[: len(audio) - len(audio) % frame].reshape(-1, frame)
    if frames.size == 0:
        return audio
    loudness = np.sqrt(np.mean(frames * frames, axis=1))
    # Relative to the loudest frame, so it adapts to quiet and loud microphones
    # alike instead of relying on one absolute threshold.
    speech = np.flatnonzero(loudness > max(loudness.max() * 0.12, 0.004))
    if speech.size == 0:
        return np.zeros(0, dtype=audio.dtype)
    pad = int(0.2 * sample_rate / frame)
    start = max(0, speech[0] - pad) * frame
    end = min(len(frames), speech[-1] + 1 + pad) * frame
    return audio[start:end]


class Transcriber:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        device, compute_type = _resolve_device_and_compute_type(cfg)
        model_path = _resolve_model_path(cfg.model_size)
        self.vad_filter = cfg.vad_filter and _vad_available()
        print(f"Loading Whisper model '{model_path}' on {device} ({compute_type})...")
        self.model = WhisperModel(
            model_path,
            device=device,
            compute_type=compute_type,
            # Anything not shipped with the app is fetched here rather than into
            # the shared Hugging Face cache, so uninstalling leaves nothing behind.
            download_root=str(data_dir() / "models"),
        )
        print("Model loaded.")

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""
        if not self.vad_filter:
            audio = _trim_silence(audio, self.cfg.sample_rate)
            if audio.size == 0:
                return ""
        language = None if self.cfg.language == "auto" else self.cfg.language
        segments, _info = self.model.transcribe(
            audio,
            language=language,
            vad_filter=self.vad_filter,
        )
        return "".join(segment.text for segment in segments).strip()
