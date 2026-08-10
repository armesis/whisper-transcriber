"""Small monochrome pill shown at the bottom of the screen while dictating."""
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QWidget

from .theme import BG, BORDER, MUTED, TEXT


class Indicator(QWidget):
    """A blinking point while recording; it holds steady while transcribing."""

    def __init__(self):
        super().__init__()
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        if sys.platform.startswith("linux"):
            # Helps this borderless "always on top" pill render correctly under
            # X11 window managers. This flag is X11-specific and unreliable
            # elsewhere - on Windows it can prevent the window from ever being
            # mapped/shown at all, so it must not be applied there.
            flags |= Qt.X11BypassWindowManagerHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(132, 30)

        self._dot_on = True
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._toggle_dot)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 5, 12, 5)
        layout.setSpacing(7)
        self._dot = QLabel("●")
        self._paint_dot(TEXT)
        self._text = QLabel("Listening...")
        self._text.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent;")
        layout.addWidget(self._dot)
        layout.addWidget(self._text)
        layout.addStretch()

        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(BG))
        painter.setPen(QColor(BORDER))
        radius = self.height() / 2
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), radius, radius)

    def _paint_dot(self, color: str):
        self._dot.setStyleSheet(f"color: {color}; font-size: 9px; background: transparent;")

    def _toggle_dot(self):
        self._dot_on = not self._dot_on
        self._paint_dot(TEXT if self._dot_on else "transparent")

    def _place_bottom_center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.center().x() - self.width() // 2
        y = screen.bottom() - self.height() - 48
        self.move(x, y)

    def show_listening(self):
        self._dot_on = True
        self._paint_dot(TEXT)
        self._text.setText("Listening...")
        self._place_bottom_center()
        self.show()
        self._pulse_timer.start(500)

    def show_transcribing(self):
        self._pulse_timer.stop()
        self._paint_dot(TEXT)
        self._text.setText("Transcribing...")

    def hide_soon(self):
        self._pulse_timer.stop()
        QTimer.singleShot(400, self.hide)

    # The engine also reports microphone level, the pasted transition, and
    # hotkey changes. The pill deliberately shows none of them, but the signals
    # are still connected, so these stay as accepted no-ops.
    def set_audio_level(self, level: float):
        pass

    def show_pasted(self):
        pass

    def set_hotkey(self, spec: str):
        pass
