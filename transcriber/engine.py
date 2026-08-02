"""Push-to-talk engine: hold the hotkey (a key, or a combo like ctrl+cmd) to
record, release any key in it to transcribe + deliver.

Exposed as a QObject so the UI can connect to its signals (it's driven from
pynput's own background thread; Qt auto-queues signal delivery into the GUI
thread for us).
"""
import threading

from pynput import keyboard
from PySide6.QtCore import QObject, Qt, Signal

from . import history
from .audio import Recorder
from .config import Config, save_config
from .model import Transcriber
from .output import deliver

# pynput reports the specific left/right variant of modifier keys on press
# (e.g. Key.ctrl_l), not the generic Key.ctrl. Normalize both directions so a
# combo like "ctrl+cmd" matches either physical Ctrl key.
_MODIFIER_ALIASES = {
    "ctrl_l": "ctrl",
    "ctrl_r": "ctrl",
    "alt_l": "alt",
    "alt_r": "alt",
    "alt_gr": "alt",
    "shift_l": "shift",
    "shift_r": "shift",
    "cmd_l": "cmd",
    "cmd_r": "cmd",
}


def _normalize(name: str) -> str:
    name = name.strip().lower()
    return _MODIFIER_ALIASES.get(name, name)


def key_event_name(key) -> str:
    """Turn a pynput key event into a normalized, config-friendly string name."""
    if isinstance(key, keyboard.Key):
        return _normalize(key.name)
    char = getattr(key, "char", None)
    return _normalize(char) if char else ""


def parse_hotkey(spec: str) -> frozenset[str]:
    """'ctrl+cmd' -> frozenset({'ctrl', 'cmd'}); also accepts a single key like 'f9'."""
    names = frozenset(_normalize(part) for part in spec.split("+") if part.strip())
    if not names:
        raise ValueError(f"Unrecognized hotkey '{spec}'.")
    return names


def format_hotkey(names) -> str:
    return "+".join(sorted(names))


def capture_next_combo(on_progress, on_captured) -> keyboard.Listener:
    """Start a listener that reports the growing set of held-down keys via
    on_progress(names) as the user presses them, then finalizes the combo via
    on_captured(names) on the first key release. Caller keeps a reference to
    the returned listener so it isn't garbage-collected early."""
    held: set[str] = set()
    captured: set[str] = set()

    def on_press(key):
        name = key_event_name(key)
        if not name:
            return
        held.add(name)
        captured.add(name)
        on_progress(sorted(captured))

    def on_release(key):
        name = key_event_name(key)
        held.discard(name)
        if captured:
            listener.stop()
            on_captured(sorted(captured))

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    return listener


class Engine(QObject):
    recordingStarted = Signal()
    recordingStopped = Signal()
    transcribing = Signal()
    transcriptReady = Signal(str)
    finished = Signal()
    statusMessage = Signal(str)
    _deliverRequested = Signal(str)

    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg
        self.target_keys = parse_hotkey(cfg.hotkey)
        self.recorder = Recorder(cfg.sample_rate)
        self.transcriber = Transcriber(cfg)
        self._held: set[str] = set()
        self._recording = False
        self._enabled = True
        self._lock = threading.Lock()
        self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        # Qt's clipboard needs COM initialized on the calling thread, which is only
        # guaranteed on the GUI thread. Route delivery through a queued signal so
        # deliver() actually runs there instead of on the worker thread.
        self._deliverRequested.connect(self._do_deliver, Qt.QueuedConnection)

    def start(self) -> None:
        self._listener.start()
        self.statusMessage.emit(f"Ready. Hold '{format_hotkey(self.target_keys)}' to dictate.")

    def set_hotkey(self, names) -> None:
        spec = format_hotkey(names)
        self.target_keys = parse_hotkey(spec)
        self._held.clear()
        self.cfg.hotkey = spec
        save_config(self.cfg)
        self.statusMessage.emit(f"Hotkey set to '{spec}'.")

    def set_enabled(self, enabled: bool) -> None:
        """Pause/resume push-to-talk, e.g. while capturing a new hotkey in the UI."""
        self._enabled = enabled
        if not enabled:
            self._held.clear()

    def _on_press(self, key):
        if not self._enabled:
            return
        name = key_event_name(key)
        if not name:
            return
        self._held.add(name)
        self._maybe_start()

    def _on_release(self, key):
        name = key_event_name(key)
        self._held.discard(name)
        if not self._enabled:
            return
        self._maybe_stop()

    def _maybe_start(self):
        with self._lock:
            if self._recording or not self.target_keys.issubset(self._held):
                return
            self._recording = True
        self.recorder.start()
        self.recordingStarted.emit()

    def _maybe_stop(self):
        with self._lock:
            if not self._recording or self.target_keys.issubset(self._held):
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
            self._deliverRequested.emit(text)
        else:
            self.statusMessage.emit("(no speech detected)")
        self.finished.emit()

    def _do_deliver(self, text: str) -> None:
        deliver(text, self.cfg)
