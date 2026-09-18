"""The push-to-talk hotkey's held-key bookkeeping.

The bug these cover: a hotkey of "cmd+ctrl" started firing on Ctrl alone after
the machine had been locked and unlocked. Locking with Win+L hands the Win
release to the secure desktop, so the app never sees it and goes on believing
Win is held - after which pressing Ctrl on its own completes the combo.
"""
import sys

import pytest
from pynput import keyboard

from transcriber.engine import (
    HeldKeys,
    format_hotkey,
    key_event_name,
    key_vk,
    parse_hotkey,
    physical_key_state,
)

# Windows virtual-key codes for the keys these tests press.
VK_LWIN, VK_LCTRL, VK_RCTRL, VK_A = 0x5B, 0xA2, 0xA3, 0x41


class FakeKeyboard:
    """Stands in for GetAsyncKeyState: a set of virtual keys that are down."""

    def __init__(self, *down):
        self.down = set(down)

    def press(self, vk):
        self.down.add(vk)

    def release(self, vk):
        self.down.discard(vk)

    def is_down(self, vk):
        return vk in self.down


def test_hotkey_spec_round_trips():
    assert parse_hotkey("cmd+ctrl") == frozenset({"cmd", "ctrl"})
    assert format_hotkey(parse_hotkey("ctrl+cmd")) == "cmd+ctrl"
    # The left/right variants pynput reports collapse onto the generic name.
    assert parse_hotkey("ctrl_l") == frozenset({"ctrl"})


def test_holds_only_while_every_key_is_down():
    hw = FakeKeyboard()
    held = HeldKeys(key_state=hw.is_down)
    combo = parse_hotkey("cmd+ctrl")

    hw.press(VK_LWIN)
    held.press("cmd", VK_LWIN)
    assert not held.holds(combo)

    hw.press(VK_LCTRL)
    held.press("ctrl", VK_LCTRL)
    assert held.holds(combo)

    hw.release(VK_LCTRL)
    held.release("ctrl", VK_LCTRL)
    assert not held.holds(combo)


def test_combo_survives_a_lock_that_swallows_the_release():
    """The regression: Win+L strands 'cmd', so Ctrl alone must not fire."""
    hw = FakeKeyboard()
    held = HeldKeys(key_state=hw.is_down)
    combo = parse_hotkey("cmd+ctrl")

    # Win+L: we see the press, the lock screen takes the release with it.
    hw.press(VK_LWIN)
    held.press("cmd", VK_LWIN)
    hw.release(VK_LWIN)  # the user really did let go; we were never told

    # Back at the desktop, Ctrl on its own must not complete the combo.
    hw.press(VK_LCTRL)
    held.press("ctrl", VK_LCTRL)
    assert not held.holds(combo)

    # ...and the real combo still works.
    hw.press(VK_LWIN)
    held.press("cmd", VK_LWIN)
    assert held.holds(combo)


def test_stranded_key_does_not_keep_a_recording_alive():
    """The same missed release seen from mid-dictation: the combo has to read
    as let go once the keys are physically up, or the microphone stays open."""
    hw = FakeKeyboard(VK_LWIN, VK_LCTRL)
    held = HeldKeys(key_state=hw.is_down)
    combo = parse_hotkey("cmd+ctrl")
    held.press("cmd", VK_LWIN)
    held.press("ctrl", VK_LCTRL)
    assert held.holds(combo)

    hw.down.clear()  # the desktop switched away; no release events arrive
    assert not held.holds(combo)


def test_both_ctrl_keys_count_as_one_held_ctrl():
    hw = FakeKeyboard()
    held = HeldKeys(key_state=hw.is_down)
    combo = parse_hotkey("ctrl")

    for vk in (VK_LCTRL, VK_RCTRL):
        hw.press(vk)
        held.press("ctrl", vk)

    hw.release(VK_LCTRL)
    held.release("ctrl", VK_LCTRL)
    assert held.holds(combo), "right Ctrl is still down"

    hw.release(VK_RCTRL)
    held.release("ctrl", VK_RCTRL)
    assert not held.holds(combo)


def test_without_a_hardware_probe_the_events_are_trusted():
    """Linux and macOS have no probe, so behaviour there is unchanged."""
    held = HeldKeys(key_state=lambda vk: True)  # stands in for "always down"
    combo = parse_hotkey("cmd+ctrl")
    held.press("cmd", VK_LWIN)
    held.press("ctrl", VK_LCTRL)
    assert held.holds(combo)
    held.release("cmd", VK_LWIN)
    assert not held.holds(combo)


def test_keys_with_no_virtual_key_code_are_left_alone():
    """Nothing to check a key against means falling back to the event stream
    rather than dropping a key that may well still be down."""
    hw = FakeKeyboard()
    held = HeldKeys(key_state=hw.is_down)
    held.press("f9", None)
    assert held.holds(parse_hotkey("f9"))
    held.release("f9", None)
    assert not held.holds(parse_hotkey("f9"))


def test_clear_forgets_everything():
    hw = FakeKeyboard(VK_LCTRL)
    held = HeldKeys(key_state=hw.is_down)
    held.press("ctrl", VK_LCTRL)
    held.clear()
    assert not held.holds(parse_hotkey("ctrl"))


def test_keycode_events_yield_a_name_and_a_virtual_key_code():
    from pynput import keyboard

    assert key_event_name(keyboard.KeyCode.from_char("a")) == "a"
    assert key_vk(keyboard.KeyCode.from_vk(VK_A)) == VK_A


@pytest.mark.skipif(
    keyboard.Key.ctrl_l.value == keyboard.Key.alt.value,
    reason="pynput's dummy backend gives every Key one value, so they all alias",
)
def test_modifier_events_yield_a_name_and_a_virtual_key_code():
    # A Key is an enum member wrapping a KeyCode, so its vk needs unwrapping;
    # a KeyCode carries .vk directly. Both shapes reach HeldKeys.
    assert key_event_name(keyboard.Key.ctrl_l) == "ctrl"
    assert key_event_name(keyboard.Key.cmd) == "cmd"
    assert key_vk(keyboard.Key.ctrl_l) == keyboard.Key.ctrl_l.value.vk
    assert key_vk(keyboard.Key.ctrl_r) != key_vk(keyboard.Key.ctrl_l)


@pytest.mark.skipif(sys.platform != "win32", reason="GetAsyncKeyState is Windows-only")
def test_windows_reads_the_real_key_state():
    """The whole fix rests on this probe existing on the platform that has the
    problem, so check the real one rather than only the stand-in above."""
    probe = physical_key_state()
    assert probe is not None
    assert probe(VK_LCTRL) in (True, False)

    # F13 is not on any ordinary keyboard, so claiming it is held is exactly the
    # lie a swallowed release tells - and it has to be seen through.
    vk_f13 = 0x7C
    held = HeldKeys()
    held.press("f13", vk_f13)
    assert not held.holds({"f13"})


@pytest.mark.skipif(sys.platform == "win32", reason="checks the non-Windows fallback")
def test_other_platforms_fall_back_to_the_event_stream():
    assert physical_key_state() is None
