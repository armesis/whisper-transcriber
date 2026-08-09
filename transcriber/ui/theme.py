"""A restrained visual system for the desktop dictation app."""
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

BG = "#111116"
SURFACE = "#191920"
SURFACE_ELEVATED = "#20202a"
BORDER = "#32323e"
TEXT = "#f3f2f7"
MUTED = "#aaa9b7"
ACCENT = "#9285ff"
ACCENT_HOVER = "#a69bff"
SUCCESS = "#72d6a0"
LISTENING = "#ff8a78"
DANGER = "#ff9085"

STYLESHEET = f"""
QWidget {{
    color: {TEXT};
    font-family: "Inter", "Noto Sans", "Ubuntu", sans-serif;
    font-size: 13px;
}}
QWidget#page {{
    background: transparent;
}}
QWidget#titleBar {{
    background: transparent;
}}
QFrame#hotkeyCard, QFrame#historyPanel {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QLabel#appName {{
    font-size: 14px;
    font-weight: 700;
}}
QLabel#statusTitle {{
    font-size: 24px;
    font-weight: 700;
}}
QLabel#statusDescription {{
    color: {MUTED};
    font-size: 13px;
}}
QLabel#muted {{
    color: {MUTED};
}}
QLabel#cardLabel {{
    font-weight: 650;
}}
QPushButton {{
    color: {TEXT};
    font-family: "Inter", "Noto Sans", "Ubuntu", sans-serif;
}}
QPushButton#hotkeyButton {{
    background-color: {ACCENT};
    border: none;
    border-radius: 10px;
    color: #171520;
    font-size: 16px;
    font-weight: 750;
    min-width: 92px;
    padding: 12px 18px;
}}
QPushButton#hotkeyButton:hover {{
    background-color: {ACCENT_HOVER};
}}
QPushButton#textButton, QPushButton#closeButton, QPushButton#dangerButton {{
    background: transparent;
    border: none;
    border-radius: 7px;
    padding: 6px 8px;
}}
QPushButton#textButton {{
    color: {MUTED};
}}
QPushButton#textButton:hover, QPushButton#closeButton:hover {{
    background: {SURFACE_ELEVATED};
    color: {TEXT};
}}
QPushButton#closeButton {{
    color: {MUTED};
    font-size: 18px;
    min-width: 28px;
}}
QPushButton#dangerButton {{
    color: {DANGER};
}}
QPushButton#dangerButton:hover {{
    background: #3a2024;
}}
QLineEdit {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 9px;
    color: {TEXT};
    padding: 8px 10px;
}}
QLineEdit:focus {{
    border-color: {ACCENT};
}}
QListWidget {{
    background: transparent;
    border: none;
    outline: none;
}}
QListWidget::item {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 10px;
    margin: 4px 1px;
}}
QListWidget::item:hover {{
    background-color: {SURFACE_ELEVATED};
}}
QListWidget::item:selected {{
    border-color: {ACCENT};
    background-color: {SURFACE_ELEVATED};
}}
QMenu {{
    background: {SURFACE_ELEVATED};
    border: 1px solid {BORDER};
    padding: 4px;
}}
QMenu::item {{
    padding: 7px 20px;
    border-radius: 5px;
}}
QMenu::item:selected {{
    background: {BORDER};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 4px 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 24px;
}}
"""


def app_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    painter.setBrush(QColor(ACCENT))
    painter.setPen(QColor(0, 0, 0, 0))
    painter.drawEllipse(2, 2, 60, 60)

    painter.setBrush(QColor(BG))
    painter.drawRoundedRect(26, 14, 12, 24, 6, 6)
    path = QPainterPath()
    path.moveTo(18, 30)
    path.cubicTo(18, 42, 46, 42, 46, 30)
    painter.setPen(QPen(QColor(BG), 3))
    painter.drawPath(path)
    painter.drawLine(32, 42, 32, 50)
    painter.drawLine(24, 50, 40, 50)

    painter.end()
    return QIcon(pixmap)
