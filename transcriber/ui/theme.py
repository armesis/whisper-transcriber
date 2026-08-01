"""Small dark theme shared by all windows. No external assets."""
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

BG = "#17151f"
CARD = "#201d2b"
CARD_HOVER = "#28243590"
BORDER = "#332f42"
TEXT = "#eae7f5"
MUTED = "#8b869c"
ACCENT = "#8b6bff"
ACCENT_HOVER = "#9d80ff"
DANGER = "#ff6b6b"

STYLESHEET = f"""
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: "Segoe UI", "Ubuntu", sans-serif;
    font-size: 13px;
}}
QFrame#card {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QLabel#title {{
    font-size: 16px;
    font-weight: 600;
}}
QLabel#muted {{
    color: {MUTED};
}}
QPushButton {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 14px;
    color: {TEXT};
}}
QPushButton:hover {{
    border-color: {ACCENT};
}}
QPushButton#accent {{
    background-color: {ACCENT};
    border: none;
    font-weight: 600;
}}
QPushButton#accent:hover {{
    background-color: {ACCENT_HOVER};
}}
QPushButton#danger {{
    color: {DANGER};
}}
QLineEdit {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 10px;
}}
QLineEdit:focus {{
    border-color: {ACCENT};
}}
QListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
}}
QListWidget::item {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 10px;
    margin: 4px 2px;
}}
QListWidget::item:selected {{
    border-color: {ACCENT};
}}
QTabWidget::pane {{
    border: none;
}}
QTabBar::tab {{
    background: transparent;
    color: {MUTED};
    padding: 8px 16px;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{
    color: {TEXT};
    border-bottom: 2px solid {ACCENT};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
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
