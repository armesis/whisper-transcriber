import argparse
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from transcriber.config import load_config
from transcriber.engine import Engine, session_warning
from transcriber.ui.indicator import Indicator
from transcriber.ui.main_window import MainWindow
from transcriber.ui.theme import STYLESHEET, app_icon
from transcriber.ui.tray import Tray


def main():
    parser = argparse.ArgumentParser(description="Local push-to-talk dictation.")
    parser.add_argument(
        "--background",
        action="store_true",
        help="start in the tray without opening the settings window",
    )
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(app_icon())

    cfg = load_config()
    engine = Engine(cfg)

    indicator = Indicator()
    indicator.set_hotkey(cfg.hotkey)
    engine.recordingStarted.connect(indicator.show_listening)
    engine.audioLevel.connect(indicator.set_audio_level)
    engine.transcribing.connect(indicator.show_transcribing)
    engine.pasted.connect(indicator.show_pasted)
    engine.finished.connect(indicator.hide_soon)
    engine.hotkeyChanged.connect(indicator.set_hotkey)
    engine.statusMessage.connect(print)

    window = MainWindow(engine)
    tray = Tray(window, app)  # noqa: F841 - keeps the tray icon alive

    # An interactive launch opens settings; the login launcher keeps the app
    # discreetly available in the background and ready for its global hotkey.
    if not args.background:
        window.show()
        window.raise_()
        window.activateWindow()

    engine.start()

    # Wayland silently swallows global key events, so the app would otherwise
    # look dead with no error anywhere. Warn after show() so this sits on top.
    if warning := session_warning():
        print(warning)
        QMessageBox.warning(window, "Global hotkeys unavailable", warning)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
