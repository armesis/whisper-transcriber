import sys

from PySide6.QtWidgets import QApplication

from transcriber.config import load_config
from transcriber.engine import Engine
from transcriber.ui.indicator import Indicator
from transcriber.ui.main_window import MainWindow
from transcriber.ui.theme import STYLESHEET, app_icon
from transcriber.ui.tray import Tray


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(app_icon())

    cfg = load_config()
    engine = Engine(cfg)

    indicator = Indicator()
    engine.recordingStarted.connect(indicator.show_listening)
    engine.transcribing.connect(indicator.show_transcribing)
    engine.finished.connect(indicator.hide_soon)
    engine.statusMessage.connect(print)

    window = MainWindow(engine)
    tray = Tray(window, app)  # noqa: F841 - keeps the tray icon alive

    engine.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
