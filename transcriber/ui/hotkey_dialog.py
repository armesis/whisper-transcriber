"""Modal 'press any key' dialog used to change the push-to-talk hotkey."""
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

from ..engine import capture_next_key
from .theme import MUTED


class _KeyCapture(QObject):
    captured = Signal(str)

    def start(self):
        self._listener = capture_next_key(self.captured.emit)


class HotkeyDialog(QDialog):
    """Shows 'press a key...', captures the next keypress, and exposes it as .result_key."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set hotkey")
        self.setFixedSize(320, 140)
        self.setModal(True)
        self.result_key: str | None = None

        layout = QVBoxLayout(self)
        self._label = QLabel("Press any key...")
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet("font-size: 18px; font-weight: 600;")
        hint = QLabel("This will be your new push-to-talk key")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(f"color: {MUTED};")
        layout.addStretch()
        layout.addWidget(self._label)
        layout.addWidget(hint)
        layout.addStretch()

        self._capture = _KeyCapture()
        self._capture.captured.connect(self._on_captured)
        self._capture.start()

    def _on_captured(self, name: str):
        self.result_key = name
        self._label.setText(name.upper())
        QTimer.singleShot(350, self.accept)
