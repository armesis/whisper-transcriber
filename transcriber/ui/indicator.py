"""Small floating pill that shows up at the bottom of the screen while dictating."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QWidget

from .theme import ACCENT, BG, TEXT


class Indicator(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(180, 44)

        self._dot_on = True
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._toggle_dot)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color: {ACCENT}; font-size: 14px; background: transparent;")
        self._text = QLabel("Listening...")
        self._text.setStyleSheet(f"color: {TEXT}; font-size: 13px; background: transparent;")
        layout.addWidget(self._dot)
        layout.addWidget(self._text)
        layout.addStretch()

        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(BG))
        painter.setPen(QColor(ACCENT))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 22, 22)

    def _toggle_dot(self):
        self._dot_on = not self._dot_on
        self._dot.setStyleSheet(
            f"color: {ACCENT if self._dot_on else 'transparent'}; "
            f"font-size: 14px; background: transparent;"
        )

    def _place_bottom_center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.center().x() - self.width() // 2
        y = screen.bottom() - self.height() - 48
        self.move(x, y)

    def show_listening(self):
        self._text.setText("Listening...")
        self._place_bottom_center()
        self.show()
        self._pulse_timer.start(500)

    def show_transcribing(self):
        self._pulse_timer.stop()
        self._dot.setStyleSheet(f"color: {ACCENT}; font-size: 14px; background: transparent;")
        self._text.setText("Transcribing...")

    def hide_soon(self):
        self._pulse_timer.stop()
        QTimer.singleShot(400, self.hide)
