"""Where the app reads its resources from and writes its state to.

Running from a source checkout, both are the checkout itself - that keeps the
development loop simple and matches how this project has always behaved. In a
frozen (PyInstaller) build the two split apart: resources live inside the
read-only bundle, while config and history have to go somewhere writable,
because an app installed under Program Files cannot write next to its .exe.
"""
import os
import sys
from pathlib import Path

APP_NAME = "WhisperTranscriber"

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def resource_dir() -> Path:
    """Read-only files shipped with the app (e.g. a vendored model)."""
    if is_frozen():
        # onedir: _MEIPASS is the _internal folder next to the .exe.
        # onefile: it is the temporary extraction directory.
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return _PROJECT_ROOT


def data_dir() -> Path:
    """Writable per-user state: config.json, history.db, downloaded models."""
    if not is_frozen():
        return _PROJECT_ROOT
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path
