"""Settings window: change the push-to-talk hotkey and browse dictation history."""
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor, QPainter
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import history
from ..engine import Engine, format_hotkey
from .hotkey_dialog import HotkeyDialog
from .theme import BG, BORDER


def _display_hotkey(spec: str) -> str:
    return spec.replace("+", " + ").upper()


class _TitleBar(QWidget):
    def __init__(self, window: "MainWindow"):
        super().__init__()
        self._window = window
        self._drag_pos: QPoint | None = None
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 8, 0)
        title = QLabel("Whisper Transcriber")
        title.setStyleSheet("font-weight: 600;")
        layout.addWidget(title)
        layout.addStretch()

        close_btn = QPushButton("x")
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(window.hide)
        layout.addWidget(close_btn)

    def mousePressEvent(self, event):
        self._drag_pos = event.globalPosition().toPoint() - self._window.pos()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None:
            self._window.move(event.globalPosition().toPoint() - self._drag_pos)


class _HotkeyTab(QWidget):
    def __init__(self, engine: Engine):
        super().__init__()
        self._engine = engine

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)

        row = QHBoxLayout()
        label_box = QVBoxLayout()
        label = QLabel("Push-to-talk hotkey")
        label.setStyleSheet("font-weight: 600;")
        desc = QLabel(
            "Hold this key (or combo, e.g. Ctrl + Win) to dictate, release either "
            "one to transcribe + paste."
        )
        desc.setWordWrap(True)
        desc.setObjectName("muted")
        label_box.addWidget(label)
        label_box.addWidget(desc)
        row.addLayout(label_box)
        row.addStretch()

        self._key_btn = QPushButton(_display_hotkey(engine.cfg.hotkey))
        self._key_btn.setObjectName("accent")
        self._key_btn.setFixedWidth(160)
        self._key_btn.clicked.connect(self._change_hotkey)
        row.addWidget(self._key_btn)

        card_layout.addLayout(row)
        layout.addWidget(card)
        layout.addStretch()

    def _change_hotkey(self):
        self._engine.set_enabled(False)
        dialog = HotkeyDialog(self)
        if dialog.exec() and dialog.result_keys:
            self._engine.set_hotkey(dialog.result_keys)
            self._key_btn.setText(_display_hotkey(format_hotkey(dialog.result_keys)))
        self._engine.set_enabled(True)


class _HistoryTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        top_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search history...")
        self._search.textChanged.connect(self.reload)
        top_row.addWidget(self._search)

        clear_btn = QPushButton("Clear all")
        clear_btn.setObjectName("danger")
        clear_btn.clicked.connect(self._clear_all)
        top_row.addWidget(clear_btn)
        layout.addLayout(top_row)

        self._list = QListWidget()
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        self._list.itemDoubleClicked.connect(self._copy_item)
        layout.addWidget(self._list)

        hint = QLabel("Double-click an entry to copy it back to your clipboard.")
        hint.setObjectName("muted")
        layout.addWidget(hint)

        self.reload()

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
        self.setWindowTitle("Whisper Transcriber")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(480, 420)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._title_bar = _TitleBar(self)
        outer.addWidget(self._title_bar)

        tabs = QTabWidget()
        self._history_tab = _HistoryTab()
        tabs.addTab(_HotkeyTab(engine), "Hotkey")
        tabs.addTab(self._history_tab, "History")
        outer.addWidget(tabs)

        engine.transcriptReady.connect(lambda _text: self._history_tab.reload())

    def showEvent(self, event):
        self._history_tab.reload()
        super().showEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(BG))
        painter.setPen(QColor(BORDER))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 14, 14)
