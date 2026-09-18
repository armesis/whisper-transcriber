"""Let the engine be imported without its native audio/inference stacks.

transcriber.engine pulls in sounddevice (which needs PortAudio present) and
faster_whisper (which needs CTranslate2) through two modules the hotkey logic
never touches. Standing in for them here keeps these tests runnable anywhere,
including on a CI box with no sound card.
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for name in ("sounddevice", "faster_whisper"):
    if name not in sys.modules:
        try:
            __import__(name)
        except Exception:
            sys.modules[name] = types.ModuleType(name)

sys.modules["sounddevice"].__dict__.setdefault("InputStream", object)
sys.modules["faster_whisper"].__dict__.setdefault("WhisperModel", object)
