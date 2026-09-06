"""Configuration for the dictation tool. Edit config.json (created on first run) to change these."""
import json
from dataclasses import dataclass, asdict
from .paths import data_dir, resource_dir

CONFIG_PATH = data_dir() / "config.json"


@dataclass
class Config:
    hotkey: str = "f9"          # push-to-talk key, or combo like "ctrl+cmd": hold to record, release to transcribe+paste
    model_size: str = "small"   # tiny/base/small/medium/large-v3 (bigger = slower + more accurate)
    device: str = "auto"        # auto/cuda/cpu
    compute_type: str = "auto"  # auto/float16/int8/int8_float16
    language: str = "auto"      # "auto" to detect, or an ISO code like "en", "tr"
    min_recording_seconds: float = 0.3
    sample_rate: int = 16000
    paste_output: bool = True   # copy transcript to clipboard and paste at the cursor
    restore_clipboard: bool = True  # restore whatever was on the clipboard before pasting
    vad_filter: bool = True     # trim silence with Silero VAD (needs the onnxruntime package)


def _bundled_model() -> str | None:
    """The single model shipped alongside the app, if there is exactly one.

    A packaged build picks which model it carries at build time, and that has to
    win over the default written here - otherwise the first launch would ignore
    the model it already has and download another one.
    """
    models = resource_dir() / "models"
    if not models.is_dir():
        return None
    names = sorted(d.name for d in models.iterdir() if (d / "model.bin").exists())
    return names[0] if len(names) == 1 else None


def load_config() -> Config:
    if CONFIG_PATH.exists():
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return Config(**{**asdict(Config()), **data})
    cfg = Config()
    if bundled := _bundled_model():
        cfg.model_size = bundled
    save_config(cfg)
    return cfg


def save_config(cfg: Config) -> None:
    CONFIG_PATH.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
