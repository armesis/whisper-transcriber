"""Push-to-talk engine: hold the hotkey (a key, or a combo like ctrl+cmd) to
record, release any key in it to transcribe + deliver.

Exposed as a QObject so the UI can connect to its signals (it's driven from
pynput's own background thread; Qt auto-queues signal delivery into the GUI
thread for us).
"""
import os
import sys
import threading

from pynput import keyboard
from PySide6.QtCore import QObject, Qt, QTimer, Signal

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


def session_warning() -> str:
    """Explain why global hotkeys can't work in this session, or '' if they can.

    pynput's Linux backend is X11 (XRecord). Under a Wayland session its listener
    starts and reports running=True, but the compositor only forwards key events
    to XWayland clients - so nothing global is ever seen: push-to-talk never
    fires and the hotkey picker captures nothing. Both fail silently, which looks
    exactly like the app being broken, so say so up front instead.
    """
    if sys.platform != "linux":
        return ""
    wayland = (
        os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
        or bool(os.environ.get("WAYLAND_DISPLAY"))
    )
    if not wayland:
        return ""
    return (
        "This is a Wayland session, and Wayland does not let applications see "
        "global key events.\n\n"
        "The push-to-talk hotkey will not fire, and the hotkey picker will not "
        "capture anything. Transcription and history still work; nothing else "
        "is wrong.\n\n"
        "Fix: log in to an Xorg session instead - pick \"Ubuntu on Xorg\" from "
        "the gear icon on the login screen. To make that the permanent default "
        "so you never have to choose again, run:\n\n"
        "    sudo sed -i 's/^#WaylandEnable=false/WaylandEnable=false/' "
        "/etc/gdm3/custom.conf\n\n"
        "then reboot."
    )


def key_event_name(key) -> str:
    """Turn a pynput key event into a normalized, config-friendly string name."""
    if isinstance(key, keyboard.Key):
        return _normalize(key.name)
    char = getattr(key, "char", None)
    return _normalize(char) if char else ""


def key_vk(key) -> int | None:
    """The OS virtual-key code behind a pynput event, when it carries one.

    A KeyCode holds its .vk directly. A Key is an enum member wrapping a
    KeyCode, and enum members do not forward attribute access to their value,
    so that case has to be unwrapped by hand.
    """
    vk = getattr(key, "vk", None)
    if vk is None:
        vk = getattr(getattr(key, "value", None), "vk", None)
    return vk if isinstance(vk, int) else None


def physical_key_state():
    """An is_down(vk) -> bool probe for the live hardware key state, or None on
    a platform that gives us no way to ask.

    Windows has GetAsyncKeyState, which reads the state of the physical key
    regardless of which window has focus - exactly what a global hotkey needs,
    and the only platform where the lock screen eats key releases (see
    HeldKeys). X11 could answer the same question through XQueryKeymap, but
    pynput does not expose it, so elsewhere we keep trusting the event stream.
    """
    if sys.platform != "win32":
        return None
    import ctypes

    user32 = ctypes.WinDLL("user32")
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short

    def is_down(vk: int) -> bool:
        # Bit 15 is "down right now". Bit 0 is "pressed since the last call",
        # which would make a key that was merely tapped look held.
        return bool(user32.GetAsyncKeyState(vk) & 0x8000)

    return is_down


class HeldKeys:
    """The set of keys currently held down, kept honest against the hardware.

    Tracking presses and releases alone is only correct while the app is there
    to hear both halves. It isn't. Lock the machine with Win+L and Windows
    switches to the secure desktop between them: the Win press arrives, the
    release is delivered somewhere this process cannot see, and "cmd" stays
    held forever. A "cmd+ctrl" hotkey then fires on Ctrl alone from the moment
    you unlock - the app behaves as though the hotkey had shrunk to whatever
    key is left, which is what makes it look like the setting was reset. Ctrl+
    Alt+Del, a UAC prompt, a fast-user switch and an RDP disconnect all strand
    a modifier the same way.

    So the press/release bookkeeping is treated as a hint, not the truth: every
    time the answer actually matters we ask the OS which of those keys is still
    physically down and drop the rest. Keys are stored by name (so a hotkey can
    say "ctrl" and mean either Ctrl key) but remembered by virtual-key code, so
    holding both Ctrl keys and letting one go still counts as holding Ctrl.
    """

    def __init__(self, key_state=None):
        self._key_state = physical_key_state() if key_state is None else key_state
        self._vks: dict[str, set[int]] = {}
        self._lock = threading.Lock()

    def press(self, name: str, vk: int | None = None) -> None:
        with self._lock:
            self._vks.setdefault(name, set())
            if vk is not None:
                self._vks[name].add(vk)

    def release(self, name: str, vk: int | None = None) -> None:
        with self._lock:
            vks = self._vks.get(name)
            if vks is None:
                return
            vks.discard(vk)
            # No vk to go on, or that was the last physical key behind this
            # name: either way the name is no longer held.
            if vk is None or not vks:
                del self._vks[name]

    def clear(self) -> None:
        with self._lock:
            self._vks.clear()

    def holds(self, target) -> bool:
        """True when every key of the combo is down right now."""
        with self._lock:
            self._reconcile()
            return set(target).issubset(self._vks)

    def _reconcile(self) -> None:
        """Forget the keys the OS says are no longer down. Caller holds _lock."""
        if self._key_state is None:
            return
        for name, vks in list(self._vks.items()):
            if not vks:
                continue  # nothing to check it against; trust the events
            still_down = {vk for vk in vks if self._key_state(vk)}
            if still_down:
                self._vks[name] = still_down
            else:
                del self._vks[name]


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
    audioLevel = Signal(float)
    transcribing = Signal()
    transcriptReady = Signal(str)
    pasted = Signal()
    hotkeyChanged = Signal(str)
    finished = Signal()
    statusMessage = Signal(str)
    _deliverRequested = Signal(str)

    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg
        self.target_keys = parse_hotkey(cfg.hotkey)
        self.recorder = Recorder(cfg.sample_rate, on_level=self.audioLevel.emit)
        self.transcriber = Transcriber(cfg)
        self._held = HeldKeys()
        self._recording = False
        self._enabled = True
        self._lock = threading.Lock()
        self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        # A release we never saw also means the stop that ends a recording never
        # arrives - lock the machine mid-sentence and the microphone would stay
        # open until the next keypress. This re-checks the hotkey against the
        # hardware while a recording is in flight, so it ends on its own.
        self._watchdog = QTimer(self)
        self._watchdog.setInterval(500)
        self._watchdog.timeout.connect(self._check_still_held)
        # Qt's clipboard needs COM initialized on the calling thread, which is only
        # guaranteed on the GUI thread. Route delivery through a queued signal so
        # deliver() actually runs there instead of on the worker thread.
        self._deliverRequested.connect(self._do_deliver, Qt.QueuedConnection)

    def start(self) -> None:
        self._listener.start()
        self._watchdog.start()
        self.statusMessage.emit(f"Ready. Hold '{format_hotkey(self.target_keys)}' to dictate.")

    def set_hotkey(self, names) -> None:
        spec = format_hotkey(names)
        self.target_keys = parse_hotkey(spec)
        self._held.clear()
        self.cfg.hotkey = spec
        save_config(self.cfg)
        self.hotkeyChanged.emit(spec)
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
        self._held.press(name, key_vk(key))
        self._maybe_start()

    def _on_release(self, key):
        name = key_event_name(key)
        self._held.release(name, key_vk(key))
        if not self._enabled:
            return
        self._maybe_stop()

    def _check_still_held(self):
        """Watchdog: end a recording whose release event never arrived."""
        if self._recording:
            self._maybe_stop()

    def _maybe_start(self):
        with self._lock:
            if self._recording or not self._held.holds(self.target_keys):
                return
            self._recording = True
        self.recorder.start()
        self.recordingStarted.emit()

    def _maybe_stop(self):
        with self._lock:
            if not self._recording or self._held.holds(self.target_keys):
                return
            self._recording = False
        audio = self.recorder.stop()
        self.recordingStopped.emit()
        duration = audio.shape[0] / self.cfg.sample_rate if audio.size else 0.0
        if duration < self.cfg.min_recording_seconds:
            self.statusMessage.emit(f"Recording too short ({duration:.2f}s), ignored.")
            # recordingStarted already moved both UIs into their listening
            # state. Even when an accidental tap is ignored, finish the UI
            # cycle so the companion bubble cannot remain stuck onscreen.
            self.finished.emit()
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
        deliver(text, self.cfg, self.pasted.emit)
