"""Companion-led feedback shown while a dictation is in progress."""
from pathlib import Path
import sys

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .theme import ACCENT, BORDER, LISTENING, MUTED, SUCCESS, SURFACE_ELEVATED, TEXT

_ASSETS = Path(__file__).resolve().parents[2] / "assets"
_WAVE_UP = _ASSETS / "whisper-companion-wave-up.png"
_WAVE_DOWN = _ASSETS / "whisper-companion-wave-down.png"


class Indicator(QWidget):
    """A compact status bubble with a small animated companion on its edge."""

    _BUBBLE = QRectF(8, 64, 322, 64)
    _COMPANION_POS = QPoint(31, 0)

    def __init__(self):
        super().__init__()
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        if sys.platform.startswith("linux"):
            flags |= Qt.X11BypassWindowManagerHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(338, 136)

        self._state = "idle"
        self._color = QColor(ACCENT)
        self._audio_level = 0.0
        self._hotkey = "F9"
        self._companion_mode = "idle"
        self._companion_phase = 0
        self._frames = {
            "up": QPixmap(str(_WAVE_UP)),
            "down": QPixmap(str(_WAVE_DOWN)),
        }

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._finish_hiding)

        self._motion_timer = QTimer(self)
        self._motion_timer.timeout.connect(self._advance_companion)

        layout = QHBoxLayout(self)
        # The cat occupies the left side above the edge. The content begins
        # beside it, so text and the microphone meter remain calm and readable.
        layout.setContentsMargins(102, 75, 18, 10)
        layout.setSpacing(10)

        self._symbol = QLabel("●")
        self._symbol.setFixedWidth(34)
        self._symbol.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._symbol)

        copy = QVBoxLayout()
        copy.setSpacing(1)
        self._title = QLabel()
        self._title.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700; background: transparent;")
        self._subtitle = QLabel()
        self._subtitle.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent;")
        copy.addWidget(self._title)
        copy.addWidget(self._subtitle)
        layout.addLayout(copy)

        self._companion = QLabel(self)
        self._companion.setAccessibleName("Animated dictation companion")
        self._companion.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._companion.setAlignment(Qt.AlignBottom | Qt.AlignHCenter)
        self._companion.setFixedSize(58, 72)
        self._companion.move(self._COMPANION_POS)
        self._set_companion_frame("down")
        self._companion.raise_()

        self.hide()

    def _set_state(self, state: str, title: str, subtitle: str, color: str, symbol: str):
        self._state = state
        self._color = QColor(color)
        self._symbol.setText(symbol)
        self._symbol.setStyleSheet(
            f"color: {color}; font-size: {'18px' if symbol == '✓' else '16px'}; "
            "font-weight: 700; background: transparent;"
        )
        self._title.setText(title)
        self._subtitle.setText(subtitle)
        self.update()

    def _set_companion_frame(self, frame: str, y_offset: int = 0):
        pixmap = self._frames[frame]
        if pixmap.isNull():
            self._companion.hide()
            return
        self._companion.setPixmap(
            pixmap.scaled(54, 70, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        self._companion.move(self._COMPANION_POS + QPoint(0, y_offset))
        self._companion.show()
        self._companion.raise_()

    def _start_companion_motion(self, mode: str):
        self._companion_mode = mode
        self._companion_phase = 0
        if mode == "listening":
            self._set_companion_frame("down", 2)
            self._motion_timer.start(520)
        elif mode == "thinking":
            self._set_companion_frame("down", 2)
            self._motion_timer.start(820)
        elif mode == "celebrating":
            self._set_companion_frame("up")
            self._motion_timer.start(180)
        else:
            self._motion_timer.stop()

    def _advance_companion(self):
        self._companion_phase = 1 - self._companion_phase
        if self._companion_mode == "listening":
            self._set_companion_frame("up" if self._companion_phase else "down", 0 if self._companion_phase else 2)
        elif self._companion_mode == "thinking":
            # A very small rise/fall reads as breathing while the model works.
            self._set_companion_frame("down", 0 if self._companion_phase else 2)
        elif self._companion_mode == "celebrating":
            self._set_companion_frame("down" if self._companion_phase else "up", 0 if self._companion_phase else 2)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(SURFACE_ELEVATED))
        painter.setPen(QColor(BORDER))
        painter.drawRoundedRect(self._BUBBLE, 15, 15)

        if self._state == "listening":
            painter.setPen(Qt.NoPen)
            painter.setBrush(self._color)
            bar_width = 4
            gap = 3
            heights = (0.50, 0.74, 1.0, 0.80, 0.58)
            start_x = 110
            center_y = self._BUBBLE.center().y()
            for index, factor in enumerate(heights):
                height = 9 + self._audio_level * 35 * factor
                x = start_x + index * (bar_width + gap)
                painter.drawRoundedRect(x, center_y - height / 2, bar_width, height, 1.5, 1.5)

    def _place_bottom_center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.center().x() - self.width() // 2
        y = screen.bottom() - self.height() - 44
        self.move(x, y)

    def _finish_hiding(self):
        self._motion_timer.stop()
        self._companion_mode = "idle"
        self.hide()

    def set_hotkey(self, spec: str):
        self._hotkey = spec.replace("+", " + ").upper()

    def show_listening(self):
        self._hide_timer.stop()
        self._audio_level = 0.0
        self._set_state("listening", "Listening", f"Release {self._hotkey}", LISTENING, "")
        self._start_companion_motion("listening")
        self._place_bottom_center()
        self.show()

    def set_audio_level(self, level: float):
        """Smooth microphone activity sent from the recorder's audio callback."""
        if self._state != "listening":
            return
        level = max(0.0, min(1.0, level))
        self._audio_level = self._audio_level * 0.42 + level * 0.58
        self.update()

    def show_transcribing(self):
        self._audio_level = 0.0
        self._set_state("transcribing", "Transcribing", "Working locally", ACCENT, "●")
        self._start_companion_motion("thinking")
        self.update()

    def show_pasted(self):
        self._audio_level = 0.0
        self._hide_timer.stop()
        self._set_state("pasted", "Pasted", "Ready where your cursor was", SUCCESS, "✓")
        self._start_companion_motion("celebrating")
        self._hide_timer.start(950)

    def hide_soon(self):
        if self._state != "pasted":
            self._hide_timer.start(450)
