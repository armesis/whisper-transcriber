"""Configuration for the dictation tool. Edit config.json (created on first run) to change these."""
import json
from dataclasses import dataclass, asdict
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


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


def load_config() -> Config:
    if CONFIG_PATH.exists():
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return Config(**{**asdict(Config()), **data})
    cfg = Config()
    save_config(cfg)
    return cfg


def save_config(cfg: Config) -> None:
    CONFIG_PATH.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
