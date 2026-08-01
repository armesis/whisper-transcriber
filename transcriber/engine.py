"""Push-to-talk engine: hold the hotkey to record, release to transcribe + deliver.

Exposed as a QObject so the UI can connect to its signals (it's driven from
pynput's own background thread; Qt auto-queues signal delivery into the GUI
thread for us).
"""
import threading

from pynput import keyboard
from PySide6.QtCore import QObject, Signal

from . import history
from .audio import Recorder
from .config import Config, save_config
from .model import Transcriber
from .output import deliver


def resolve_key(name: str):
    """Map a config string like 'f9' or 'caps_lock' to a pynput key, or a plain character."""
    name = name.strip().lower()
    special = getattr(keyboard.Key, name, None)
    if special is not None:
        return special
    if len(name) == 1:
        return name
    raise ValueError(
        f"Unrecognized hotkey '{name}'. Use names like 'f9', 'caps_lock', "
        f"'right_ctrl', or a single character like 'z'."
    )


def key_to_name(key) -> str:
    """Inverse of resolve_key: turn a pynput key event into a config-friendly string."""
    if isinstance(key, keyboard.Key):
        return key.name
    char = getattr(key, "char", None)
    return (char or "").lower()


def _key_matches(pressed_key, target) -> bool:
    if isinstance(target, keyboard.Key):
        return pressed_key == target
    char = getattr(pressed_key, "char", None)
    return char is not None and char.lower() == target


def capture_next_key(callback) -> keyboard.Listener:
    """Start a one-shot listener that calls callback(name) with the next key pressed,
    then stops itself. Caller keeps a reference so it isn't garbage-collected early."""

    def on_press(key):
        listener.stop()
        callback(key_to_name(key))

    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    return listener


class Engine(QObject):
    recordingStarted = Signal()
    recordingStopped = Signal()
    transcribing = Signal()
    transcriptReady = Signal(str)
    finished = Signal()
    statusMessage = Signal(str)

    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg
        self.target_key = resolve_key(cfg.hotkey)
        self.recorder = Recorder(cfg.sample_rate)
        self.transcriber = Transcriber(cfg)
        self._recording = False
        self._enabled = True
        self._lock = threading.Lock()
        self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)

    def start(self) -> None:
        self._listener.start()
        self.statusMessage.emit(f"Ready. Hold '{self.cfg.hotkey}' to dictate.")

    def set_hotkey(self, name: str) -> None:
        self.target_key = resolve_key(name)
        self.cfg.hotkey = name
        save_config(self.cfg)
        self.statusMessage.emit(f"Hotkey set to '{name}'.")

    def set_enabled(self, enabled: bool) -> None:
        """Pause/resume push-to-talk, e.g. while capturing a new hotkey in the UI."""
        self._enabled = enabled

    def _on_press(self, key):
        if not self._enabled or not _key_matches(key, self.target_key):
            return
        with self._lock:
            if self._recording:
                return
            self._recording = True
        self.recorder.start()
        self.recordingStarted.emit()

    def _on_release(self, key):
        if not self._enabled or not _key_matches(key, self.target_key):
            return
        with self._lock:
            if not self._recording:
                return
            self._recording = False
        audio = self.recorder.stop()
        self.recordingStopped.emit()
        duration = audio.shape[0] / self.cfg.sample_rate if audio.size else 0.0
        if duration < self.cfg.min_recording_seconds:
            self.statusMessage.emit(f"Recording too short ({duration:.2f}s), ignored.")
            return
        threading.Thread(target=self._transcribe_and_deliver, args=(audio,), daemon=True).start()

    def _transcribe_and_deliver(self, audio):
        self.transcribing.emit()
        text = self.transcriber.transcribe(audio)
        if text:
            history.add_entry(text)
            self.transcriptReady.emit(text)
            deliver(text, self.cfg)
        else:
            self.statusMessage.emit("(no speech detected)")
        self.finished.emit()
