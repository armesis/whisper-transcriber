"""Delivers transcribed text to wherever the user's cursor currently is.

Uses Qt's clipboard (QClipboard) instead of pyperclip/xclip so it works the same
way on Windows and Linux (X11) without extra system packages.
"""
import time

from PySide6.QtWidgets import QApplication
from pynput.keyboard import Controller, Key

from .config import Config

_kb = Controller()


def deliver(text: str, cfg: Config) -> None:
    if not text:
        return

    if not cfg.paste_output:
        return

    clipboard = QApplication.clipboard()
    previous_clipboard = clipboard.text() if cfg.restore_clipboard else None

    clipboard.setText(text)
    time.sleep(0.05)  # let the OS clipboard settle before the paste hotkey fires

    with _kb.pressed(Key.ctrl):
        _kb.press("v")
        _kb.release("v")

    if cfg.restore_clipboard and previous_clipboard is not None:
        time.sleep(0.2)  # let the target app read the clipboard before we overwrite it
        clipboard.setText(previous_clipboard)
