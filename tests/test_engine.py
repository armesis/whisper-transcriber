"""The engine's end of the same story: which key events start and stop a recording.

These drive the real Engine, with the microphone, the model and the hardware
key probe stubbed out, so the push-to-talk state machine is what is under test.
"""
import numpy as np
import pytest
from pynput import keyboard
from PySide6.QtCore import QCoreApplication

from transcriber import engine as engine_module
from transcriber.config import Config
from transcriber.engine import Engine, HeldKeys

pytestmark = pytest.mark.skipif(
    keyboard.Key.ctrl_l.value == keyboard.Key.alt.value,
    reason="pynput's dummy backend gives every Key one value, so they all alias",
)

CMD, CTRL = keyboard.Key.cmd, keyboard.Key.ctrl


class FakeRecorder:
    def __init__(self, *_args, **_kwargs):
        self.running = False
        self.starts = 0

    def start(self):
        self.running = True
        self.starts += 1

    def stop(self):
        self.running = False
        return np.zeros(0, dtype=np.float32)


@pytest.fixture(scope="module")
def qt_app():
    return QCoreApplication.instance() or QCoreApplication([])


@pytest.fixture
def keyboard_hardware():
    """The set of virtual keys physically down, as GetAsyncKeyState would see it."""

    class Hardware:
        def __init__(self):
            self.down = set()

        def press(self, key):
            self.down.add(engine_module.key_vk(key))

        def release(self, key):
            self.down.discard(engine_module.key_vk(key))

        def is_down(self, vk):
            return vk in self.down

    return Hardware()


@pytest.fixture
def engine(qt_app, keyboard_hardware, monkeypatch):
    monkeypatch.setattr(engine_module, "Recorder", FakeRecorder)
    monkeypatch.setattr(engine_module, "Transcriber", lambda cfg: object())
    monkeypatch.setattr(engine_module, "save_config", lambda cfg: None)
    built = Engine(Config(hotkey="cmd+ctrl"))
    built._held = HeldKeys(key_state=keyboard_hardware.is_down)
    return built


def press(engine, keyboard_hardware, key):
    keyboard_hardware.press(key)
    engine._on_press(key)


def release(engine, keyboard_hardware, key):
    keyboard_hardware.release(key)
    engine._on_release(key)


def test_the_full_combo_starts_and_stops_a_recording(engine, keyboard_hardware):
    press(engine, keyboard_hardware, CMD)
    assert not engine.recorder.running, "half the combo is not the combo"

    press(engine, keyboard_hardware, CTRL)
    assert engine.recorder.running

    release(engine, keyboard_hardware, CTRL)
    assert not engine.recorder.running


def test_ctrl_alone_still_does_nothing_after_a_lock_screen(engine, keyboard_hardware):
    """The reported bug. Win+L: the press is seen, the release goes to the lock
    screen, and the app is left believing Win is held down. Pressing Ctrl on its
    own afterwards used to start recording, as if the hotkey had become 'ctrl'."""
    press(engine, keyboard_hardware, CMD)
    keyboard_hardware.release(CMD)  # let go behind the lock screen; no event

    press(engine, keyboard_hardware, CTRL)
    assert not engine.recorder.running

    release(engine, keyboard_hardware, CTRL)
    press(engine, keyboard_hardware, CMD)
    press(engine, keyboard_hardware, CTRL)
    assert engine.recorder.running, "the real combo still has to work"


def test_the_watchdog_closes_a_recording_the_lock_screen_interrupted(engine, keyboard_hardware):
    """Locking mid-sentence takes the release with it, which would otherwise
    leave the microphone open until the next keypress."""
    press(engine, keyboard_hardware, CMD)
    press(engine, keyboard_hardware, CTRL)
    assert engine.recorder.running

    keyboard_hardware.down.clear()  # desktop switched away; no release events
    assert engine.recorder.running, "nothing has looked yet"

    engine._check_still_held()
    assert not engine.recorder.running


def test_a_recording_in_progress_is_left_alone_by_the_watchdog(engine, keyboard_hardware):
    press(engine, keyboard_hardware, CMD)
    press(engine, keyboard_hardware, CTRL)
    for _ in range(5):
        engine._check_still_held()
    assert engine.recorder.running
    assert engine.recorder.starts == 1


def test_changing_the_hotkey_forgets_what_was_held(engine, keyboard_hardware):
    press(engine, keyboard_hardware, CMD)
    engine.set_hotkey(["ctrl"])
    assert engine.cfg.hotkey == "ctrl"

    press(engine, keyboard_hardware, CTRL)
    assert engine.recorder.running
