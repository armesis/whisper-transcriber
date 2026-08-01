"""Delivers transcribed text to wherever the user's cursor currently is.

Uses Qt's clipboard (QClipboard) instead of pyperclip/xclip so it works the same
way on Windows and Linux (X11) without extra system packages. Must run on the
Qt GUI thread (Engine marshals it there via a queued signal) - QClipboard isn't
thread-safe, and on Windows the underlying OLE clipboard needs COM initialized,
which is only guaranteed on that thread. Delays are done with QTimer instead of
time.sleep so we never block the GUI event loop.
"""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from pynput.keyboard import Controller, Key

from .config import Config

_kb = Controller()


def deliver(text: str, cfg: Config) -> None:
    if not text or not cfg.paste_output:
        return

    clipboard = QApplication.clipboard()
    previous_clipboard = clipboard.text() if cfg.restore_clipboard else None
    clipboard.setText(text)

    # let the OS clipboard settle before the paste hotkey fires
    QTimer.singleShot(50, lambda: _paste_and_restore(clipboard, previous_clipboard, cfg))


def _paste_and_restore(clipboard, previous_clipboard, cfg: Config) -> None:
    with _kb.pressed(Key.ctrl):
        _kb.press("v")
        _kb.release("v")

    if cfg.restore_clipboard and previous_clipboard is not None:
        # let the target app read the clipboard before we overwrite it
        QTimer.singleShot(200, lambda: clipboard.setText(previous_clipboard))
