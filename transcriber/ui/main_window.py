"""A focused control surface for local push-to-talk dictation."""
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import history
from ..engine import Engine, format_hotkey, session_warning
from .hotkey_dialog import HotkeyDialog
from .theme import ACCENT, BG, BORDER, LISTENING, MUTED, SUCCESS, TEXT

_CAT_ASSET = Path(__file__).resolve().parents[2] / "assets" / "whisper-cat-tight.png"


def _display_hotkey(spec: str) -> str:
    return spec.replace("+", " + ").upper()


class _TitleBar(QWidget):
    def __init__(self, window: "MainWindow"):
        super().__init__()
        self._window = window
        self._drag_pos: QPoint | None = None
        self.setObjectName("titleBar")
        self.setFixedHeight(48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 10, 0)
        layout.setSpacing(8)

        mark = QLabel("●")
        mark.setStyleSheet(f"color: {ACCENT}; font-size: 16px; background: transparent;")
        layout.addWidget(mark)

        title = QLabel("Whisper")
        title.setObjectName("appName")
        layout.addWidget(title)
        layout.addStretch()

        history_btn = QPushButton("History")
        history_btn.setObjectName("textButton")
        history_btn.clicked.connect(window.show_history)
        layout.addWidget(history_btn)

        close_btn = QPushButton("×")
        close_btn.setObjectName("closeButton")
        close_btn.setFixedSize(30, 30)
        close_btn.setToolTip("Hide Whisper")
        close_btn.clicked.connect(window.hide)
        layout.addWidget(close_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self._window.pos()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self._window.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


class _HomeView(QWidget):
    def __init__(self, engine: Engine):
        super().__init__()
        self._engine = engine
        self.setObjectName("page")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 22, 30, 26)
        layout.setSpacing(0)

        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self._state_dot = QLabel("●")
        self._state_dot.setStyleSheet(f"color: {SUCCESS}; font-size: 14px; background: transparent;")
        status_row.addWidget(self._state_dot, alignment=Qt.AlignTop)

        status_copy = QVBoxLayout()
        status_copy.setSpacing(5)
        self._state_title = QLabel("Ready")
        self._state_title.setObjectName("statusTitle")
        status_copy.addWidget(self._state_title)
        self._state_description = QLabel()
        self._state_description.setObjectName("statusDescription")
        self._state_description.setWordWrap(True)
        status_copy.addWidget(self._state_description)
        status_row.addLayout(status_copy)
        status_row.addStretch()
        layout.addLayout(status_row)

        layout.addSpacing(26)

        card = QFrame()
        card.setObjectName("hotkeyCard")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 16, 16)
        card_layout.setSpacing(14)

        key_copy = QVBoxLayout()
        key_copy.setSpacing(3)
        label = QLabel("Push to talk")
        label.setObjectName("cardLabel")
        key_copy.addWidget(label)
        hint = QLabel("Change the key anytime")
        hint.setObjectName("muted")
        key_copy.addWidget(hint)
        card_layout.addLayout(key_copy)
        card_layout.addStretch()

        self._key_btn = QPushButton(_display_hotkey(engine.cfg.hotkey))
        self._key_btn.setObjectName("hotkeyButton")
        self._key_btn.clicked.connect(self._change_hotkey)
        card_layout.addWidget(self._key_btn)
        layout.addWidget(card)

        layout.addSpacing(14)
        footer = QHBoxLayout()
        details = QLabel("Small model  ·  Auto language  ·  On-device")
        details.setObjectName("muted")
        footer.addWidget(details, alignment=Qt.AlignVCenter)
        footer.addStretch()

        companion = QLabel()
        companion.setAccessibleName("Decorative resting cat")
        cat = QPixmap(str(_CAT_ASSET))
        if not cat.isNull():
            companion.setPixmap(cat.scaled(52, 52, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            footer.addWidget(companion, alignment=Qt.AlignRight | Qt.AlignVCenter)

        layout.addLayout(footer)
        layout.addStretch()

        if session_warning():
            warning = QLabel("Global hotkeys need an Xorg session on Linux.")
            warning.setObjectName("muted")
            warning.setAlignment(Qt.AlignCenter)
            layout.addWidget(warning)

        self.set_state("ready")

    def _change_hotkey(self):
        self._engine.set_enabled(False)
        dialog = HotkeyDialog(self)
        if dialog.exec() and dialog.result_keys:
            self._engine.set_hotkey(dialog.result_keys)
            self._key_btn.setText(_display_hotkey(format_hotkey(dialog.result_keys)))
        self._engine.set_enabled(True)
        self.set_state("ready")

    def set_state(self, state: str):
        key = _display_hotkey(self._engine.cfg.hotkey)
        states = {
            "ready": ("Ready", f"Hold {key} while you speak. Release it to transcribe and paste.", SUCCESS),
            "listening": ("Listening", f"Speak naturally. Release {key} when you are done.", LISTENING),
            "transcribing": ("Transcribing", "Working locally on your device.", ACCENT),
        }
        title, description, color = states[state]
        self._state_title.setText(title)
        self._state_description.setText(description)
        self._state_dot.setStyleSheet(f"color: {color}; font-size: 14px; background: transparent;")


class _HistoryView(QWidget):
    def __init__(self, back):
        super().__init__()
        self.setObjectName("page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 22)
        layout.setSpacing(12)

        top_row = QHBoxLayout()
        back_btn = QPushButton("‹  Back")
        back_btn.setObjectName("textButton")
        back_btn.clicked.connect(back)
        top_row.addWidget(back_btn)
        title = QLabel("History")
        title.setObjectName("appName")
        top_row.addWidget(title)
        top_row.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("dangerButton")
        clear_btn.clicked.connect(self._clear_all)
        top_row.addWidget(clear_btn)
        layout.addLayout(top_row)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search your transcriptions")
        self._search.textChanged.connect(self.reload)
        layout.addWidget(self._search)

        self._list = QListWidget()
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        self._list.itemDoubleClicked.connect(self._copy_item)
        layout.addWidget(self._list)

        hint = QLabel("Double-click an entry to copy it.")
        hint.setObjectName("muted")
        layout.addWidget(hint)

    def reload(self):
        query = self._search.text().strip().lower()
        self._list.clear()
        for entry in history.get_entries():
            if query and query not in entry.text.lower():
                continue
            item = QListWidgetItem(f"{entry.created_at}\n{entry.text}")
            item.setData(Qt.UserRole, entry.id)
            item.setData(Qt.UserRole + 1, entry.text)
            self._list.addItem(item)

    def _copy_item(self, item: QListWidgetItem):
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(item.data(Qt.UserRole + 1))

    def _show_context_menu(self, pos):
        item = self._list.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        copy_action = menu.addAction("Copy")
        delete_action = menu.addAction("Delete")
        action = menu.exec(self._list.mapToGlobal(pos))
        if action == copy_action:
            self._copy_item(item)
        elif action == delete_action:
            history.delete_entry(item.data(Qt.UserRole))
            self.reload()

    def _clear_all(self):
        if QMessageBox.question(self, "Clear history", "Delete all saved transcriptions?") == QMessageBox.Yes:
            history.clear_all()
            self.reload()


class MainWindow(QWidget):
    def __init__(self, engine: Engine):
        super().__init__()
        self.setWindowTitle("Whisper")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(460, 340)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(_TitleBar(self))
        self._pages = QStackedWidget()
        self._home = _HomeView(engine)
        self._history = _HistoryView(self.show_home)
        self._pages.addWidget(self._home)
        self._pages.addWidget(self._history)
        outer.addWidget(self._pages)

        engine.recordingStarted.connect(lambda: self._home.set_state("listening"))
        engine.transcribing.connect(lambda: self._home.set_state("transcribing"))
        engine.finished.connect(lambda: self._home.set_state("ready"))
        engine.transcriptReady.connect(lambda _text: self._history.reload())

    def show_history(self):
        self._history.reload()
        self._pages.setCurrentWidget(self._history)

    def show_home(self):
        self._pages.setCurrentWidget(self._home)

    def showEvent(self, event):
        self._history.reload()
        super().showEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(BG))
        painter.setPen(QColor(BORDER))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 14, 14)
