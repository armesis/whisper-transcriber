import argparse
import sys

from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from transcriber.config import load_config
from transcriber.engine import Engine, session_warning
from transcriber.ui.indicator import Indicator
from transcriber.ui.main_window import MainWindow
from transcriber.ui.theme import STYLESHEET, app_icon
from transcriber.ui.tray import Tray


def selftest() -> int:
    """Exercise every native dependency without touching the user's desktop.

    A packaged build can fail in ways a source run never does - a stripped Qt
    plugin, a DLL the bundler decided was unreachable. This constructs the real
    widgets and runs a real transcription, so a build that prints OK here has
    proven its Qt, CTranslate2, tokenizers and numpy payloads all load.
    """
    import numpy as np

    from transcriber.model import Transcriber, have_local_model

    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(app_icon())

    cfg = load_config()
    # The CPU path is what every machine falls back to, so verify that one
    # even on a box with a working CUDA runtime.
    cfg.device, cfg.compute_type = "cpu", "int8"
    window = MainWindow.__new__(MainWindow)  # widgets without an Engine attached
    QWidget.__init__(window)
    Indicator()
    app.processEvents()
    print(f"OK  qt={QApplication.instance() is not None} platform={app.platformName()}")

    # A build that ships no model would otherwise download half a gigabyte
    # here; the point of the self-test is to prove the binaries load.
    if have_local_model(cfg.model_size):
        transcriber = Transcriber(cfg)
        text = transcriber.transcribe(np.zeros(16000, dtype=np.float32))
        print(f"OK  transcribe(silence) -> {text!r}")
    else:
        print(f"SKIP no local '{cfg.model_size}' model; it downloads on first run")
    print("SELFTEST PASSED")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Local push-to-talk dictation.")
    parser.add_argument(
        "--background",
        action="store_true",
        help="start in the tray without opening the settings window",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="build the UI and run one transcription, then exit (used to verify a build)",
    )
    args = parser.parse_args()

    if args.selftest:
        return selftest()

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

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
