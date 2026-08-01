"""System tray icon: open the settings window or quit from here.

Note: on Ubuntu with a stock GNOME session the tray icon may not appear unless
the "AppIndicator and KStatusNotifierItem Support" GNOME Shell extension is
installed - see the README.
"""
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .main_window import MainWindow
from .theme import app_icon


class Tray(QSystemTrayIcon):
    def __init__(self, window: MainWindow, app: QApplication):
        super().__init__(app_icon())
        self._window = window
        self._app = app
        self.setToolTip("Whisper Transcriber")

        menu = QMenu()
        open_action = menu.addAction("Open Whisper Transcriber")
        open_action.triggered.connect(self._show_window)
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(app.quit)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

        if QSystemTrayIcon.isSystemTrayAvailable():
            self.show()
        else:
            print(
                "No system tray available on this desktop - the settings window "
                "won't be reachable via a tray icon. Keep it open, or re-run "
                "main.py to bring it back."
            )

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self._show_window()

    def _show_window(self):
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()
