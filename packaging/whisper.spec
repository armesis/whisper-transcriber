# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for a self-contained, CPU-only Windows app.

Tuned for footprint. Every knob is set by build.ps1 through the environment:

  WT_MODEL        directory under ./models to vendor inside the build, or ""
                  to ship no model and download one on first run
  WT_VAD          "1" bundles onnxruntime for the Silero VAD, "0" leaves it
                  out (~45 MB) for the energy-based trim in model.py
  WT_CONSOLE      "1" keeps a console window attached so print() is visible
  WT_KEEP_ALL_QT  "1" skips the Qt pruning below and ships every Qt DLL
"""
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

PROJECT = Path(SPECPATH).resolve().parent

VENDOR_MODEL = os.environ.get("WT_MODEL", "")
WITH_VAD = os.environ.get("WT_VAD", "0") == "1"
CONSOLE = os.environ.get("WT_CONSOLE", "0") == "1"
# Escape hatch: keeps every Qt DLL the hook found, including the 20 MB software
# OpenGL fallback, for the rare machine where the pruned build misbehaves.
KEEP_ALL_QT = os.environ.get("WT_KEEP_ALL_QT", "0") == "1"

# --- what to ship -----------------------------------------------------------

datas = []
if VENDOR_MODEL:
    model_dir = PROJECT / "models" / VENDOR_MODEL
    if not (model_dir / "model.bin").exists():
        raise SystemExit(f"No CTranslate2 model at {model_dir} (expected model.bin)")
    for item in model_dir.iterdir():
        if item.is_file():
            datas.append((str(item), f"models/{VENDOR_MODEL}"))

if WITH_VAD:
    # get_assets_path() looks the ONNX graph up next to faster_whisper/assets.
    datas += [
        (src, dst)
        for src, dst in collect_data_files("faster_whisper")
        if src.endswith(".onnx")
    ]

# --- what to leave out ------------------------------------------------------

# Only QtCore/QtGui/QtWidgets are used. Naming the rest as excludes stops
# PyInstaller pulling in their DLLs, which is where most of PySide6's 630 MB is
# (Qt6WebEngineCore.dll alone is 195 MB).
import PySide6  # noqa: E402

QT_KEEP = {"QtCore", "QtGui", "QtWidgets"}
qt_modules = {
    name.split(".")[0]
    for name in os.listdir(Path(PySide6.__file__).parent)
    if name.startswith("Qt") and name.endswith(".pyd")
}

excludes = [f"PySide6.{name}" for name in sorted(qt_modules - QT_KEEP)]
excludes += [
    "PySide6.scripts",
    "PySide6.support",
    # Media decoding we never reach - see packaging/rthook_stub_av.py.
    "av",
    # Development, packaging and notebook machinery that nothing here imports.
    "pip",
    "setuptools",
    "pkg_resources",
    "PyInstaller",
    "tkinter",
    "unittest",
    "pydoc_data",
    "doctest",
    "lib2to3",
    "test",
    "IPython",
    "matplotlib",
    "PIL",
    "scipy",
    "pandas",
    "pyperclip",
    # Optional Hugging Face extras; the hub falls back to plain HTTP without them.
    "hf_xet",
    "fsspec",
    "numpy.f2py",
    "numpy.distutils",
]
if not WITH_VAD:
    excludes += ["onnxruntime", "google", "google.protobuf", "flatbuffers"]

a = Analysis(
    [str(PROJECT / "main.py")],
    pathex=[str(PROJECT)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[str(PROJECT / "packaging" / "rthook_stub_av.py")],
    excludes=excludes,
    noarchive=False,
    optimize=2,
)

# PyInstaller's Qt hook copies plugin families wholesale. A frameless widget app
# needs the platform integration and a style; the rest (3D renderers, multimedia
# backends, SQL drivers, TLS backends, image codecs for images we never load) is
# dead weight. Every icon in this app is drawn with QPainter, so no image or
# icon-engine plugin is ever asked for.
PLUGIN_KEEP = ("platforms", "styles", "platformthemes")


def _wanted(entry):
    dest = entry[0].replace("\\", "/")
    if "/plugins/" in dest:
        family = dest.split("/plugins/", 1)[1].split("/", 1)[0]
        if family not in PLUGIN_KEEP:
            return False
        # Only the default Windows platform plugin plus the two headless ones
        # that make --selftest and CI runs possible.
        if family == "platforms":
            return Path(dest).stem in {"qwindows", "qminimal", "qoffscreen"}
        return True
    # Qt ships its translations for every language it supports; the UI is
    # English-only and never calls QTranslator.
    if "/translations/" in dest or dest.endswith(".qm"):
        return False
    return True


a.datas = [entry for entry in a.datas if _wanted(entry)]
a.binaries = [entry for entry in a.binaries if _wanted(entry)]


def _prune_unreachable_qt(binaries):
    """Drop Qt DLLs nothing left in the build actually links against.

    Excluding PySide6.QtQuick stops its Python binding being collected, but the
    hook still copies Qt6Quick.dll and friends alongside it. Rather than curate
    a denylist that silently rots at the next Qt release, read the real import
    tables: start from the binding modules and the plugins Qt loads at runtime,
    follow every dependency, and keep only what that reaches.
    """
    from PyInstaller.depend import bindepend

    by_name = {}
    for dest, src, kind in binaries:
        by_name.setdefault(Path(dest).name.lower(), src)

    roots = [
        src
        for dest, src, kind in binaries
        if dest.replace("\\", "/").startswith("PySide6/")
        and (dest.endswith(".pyd") or "/plugins/" in dest.replace("\\", "/"))
    ]

    reached, queue = set(), list(roots)
    while queue:
        current = queue.pop()
        if current in reached:
            continue
        reached.add(current)
        try:
            imports = bindepend.get_imports(current)
        except Exception:
            continue
        for name, _ in imports:
            src = by_name.get(name.lower())
            if src is not None and src not in reached:
                queue.append(src)

    def keep(entry):
        dest, src, _kind = entry
        name = Path(dest).name.lower()
        optional = name.startswith("qt6") or name == "opengl32sw.dll"
        return not optional or src in reached

    return [entry for entry in binaries if keep(entry)]


if not KEEP_ALL_QT:
    a.binaries = _prune_unreachable_qt(a.binaries)


def _colocate_msvc_runtime(binaries):
    """Put the Visual C++ runtime beside every DLL that needs it.

    Python loads extension modules with LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR, so a
    dependency is looked for in the folder of the module being loaded and then
    in the system directories - not in sibling folders. PyInstaller collects
    MSVCP140.dll into the PySide6 folder because that is the wheel it came
    from, which leaves ctranslate2.dll resolving it from System32. That works on
    any developer machine, and on most others, because so much software installs
    the redistributable - but "most" is not "any", and when it is missing the
    app dies on import with nothing useful to say. A few hundred kilobytes of
    duplication buys a build that genuinely stands alone.
    """
    from PyInstaller.depend import bindepend

    def is_runtime(name):
        return name.lower().startswith(("msvcp140.", "msvcp140_", "vcruntime140", "concrt140"))

    available = {}
    for dest, src, _kind in binaries:
        name = Path(dest).name
        if is_runtime(name):
            available.setdefault(name.lower(), src)

    present = {(Path(dest).parent.as_posix(), Path(dest).name.lower()) for dest, _s, _k in binaries}

    extra = []
    for dest, src, _kind in binaries:
        folder = Path(dest).parent
        try:
            imports = bindepend.get_imports(src)
        except Exception:
            continue
        for name, _ in imports:
            key = name.lower()
            if not is_runtime(name) or key not in available:
                continue
            if (folder.as_posix(), key) in present:
                continue
            present.add((folder.as_posix(), key))
            extra.append((str(folder / name), available[key], "BINARY"))
    return binaries + extra


a.binaries = _colocate_msvc_runtime(a.binaries)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WhisperTranscriber",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=CONSOLE,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="WhisperTranscriber",
)
