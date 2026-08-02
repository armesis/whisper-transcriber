"""Modal 'press a key combination' dialog used to change the push-to-talk hotkey."""
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

from ..engine import capture_next_combo, format_hotkey
from .theme import MUTED


class _KeyCapture(QObject):
    progress = Signal(list)
    captured = Signal(list)

    def start(self):
        self._listener = capture_next_combo(self.progress.emit, self.captured.emit)


class HotkeyDialog(QDialog):
    """Shows 'press a key combination...', captures every key held down until the
    first release, and exposes the result as .result_keys (a sorted list)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set hotkey")
        self.setFixedSize(320, 140)
        self.setModal(True)
        self.result_keys: list[str] | None = None

        layout = QVBoxLayout(self)
        self._label = QLabel("Press a key combination...")
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet("font-size: 18px; font-weight: 600;")
        hint = QLabel("Hold multiple keys together, e.g. Ctrl + Win, then let go")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(f"color: {MUTED};")
        layout.addStretch()
        layout.addWidget(self._label)
        layout.addWidget(hint)
        layout.addStretch()

        self._capture = _KeyCapture()
        self._capture.progress.connect(self._on_progress)
        self._capture.captured.connect(self._on_captured)
        self._capture.start()

    def _on_progress(self, names: list[str]):
        self._label.setText(format_hotkey(names).replace("+", " + ").upper())

    def _on_captured(self, names: list[str]):
        self.result_keys = names
        self._label.setText(format_hotkey(names).replace("+", " + ").upper())
        QTimer.singleShot(350, self.accept)
