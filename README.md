# whisper-transcriber

Push-to-talk dictation for your desktop. Hold a hotkey, speak, release — your
speech is transcribed locally with
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) and pasted at your
cursor wherever you're typing.

Runs fully offline (the `small` model is vendored in `models/`, no download or
API calls needed) and uses your GPU automatically when one is available. Works
on Windows and Ubuntu/Linux from the same codebase.

The UI stays out of the way: a small monochrome window for the hotkey and a
searchable history, plus a compact pill near the bottom of the screen whose
point blinks while you record and holds steady while the model transcribes.

## Setup

```bash
cd whisper-transcriber
python -m venv .venv
```

Windows (PowerShell):
```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Ubuntu/Linux:
```bash
source .venv/bin/activate
sudo apt install libportaudio2   # PortAudio runtime for sounddevice
pip install -r requirements.txt
```

## Run

Windows:
```bash
python main.py
```

Ubuntu/Linux:
```bash
./run.sh
```

A tray icon appears (a purple mic in a circle). Click it to open the app, where
you can change the push-to-talk hotkey or open the searchable transcription
history. The default hotkey is **F9**; releasing any key in a multi-key combo
stops the recording.

To dictate: focus the field where the result should appear, hold the hotkey,
speak, then release. The pill reads **Listening...** with a blinking point,
then **Transcribing...** with the point held steady, and disappears once the
text has been inserted at your cursor. Accidental short taps are ignored and
the pill closes without getting stuck.

Closing the main window only hides it; the app keeps running in the tray. Quit
from the tray menu.

### Start automatically on Ubuntu/Linux

Run this once from the cloned project directory:

```bash
./install-autostart.sh
```

The installer detects the checkout's absolute path and creates a per-user
launcher. On the next graphical login, Whisper starts quietly in the tray with
`--background`; you do not need to open a terminal first.

## Configuration

Everything is in the UI now. Advanced settings (model size, device, language,
whether to paste automatically) still live in `config.json`, created on first
run next to `main.py` when you run from a checkout, or in
`%LOCALAPPDATA%\WhisperTranscriber\` when you run a packaged build (which
cannot write next to its own `.exe`). `history.db` follows the same rule.

| key | meaning |
|---|---|
| `hotkey` | managed by the UI, but editable here too |
| `model_size` | `tiny`, `base`, `small`, `medium`, `large-v3` — only `small` is vendored; other sizes download from Hugging Face on first use |
| `device` | `auto`, `cuda`, or `cpu` |
| `compute_type` | `auto`, `float16`, `int8`, `int8_float16` |
| `language` | `auto` to detect, or an ISO code like `en`, `tr` |
| `min_recording_seconds` | ignores accidental taps shorter than this |
| `paste_output` | `true` to paste at the cursor, `false` to only save to history |
| `restore_clipboard` | restore your previous clipboard contents after pasting |
| `vad_filter` | `true` to trim silence with the Silero VAD; ignored, with a cheaper energy-based trim used instead, when the build does not ship `onnxruntime` |

## Build a standalone Windows app

`packaging\build.ps1` freezes everything into `build\dist\WhisperTranscriber\`
— a folder you can copy to any 64-bit Windows 10/11 machine and run. No Python,
no pip, no Visual C++ redistributable, no GPU. CUDA is still picked up
automatically on machines that have it.

```powershell
.\packaging\build.ps1 -Zip
```

That default ships **no model**: the app downloads the one named in
`config.json` the first time it starts and caches it under `%LOCALAPPDATA%`. It
is the smallest thing to hand someone, at the cost of needing a connection once.

To make it fully offline, fetch a model and bake it in:

```powershell
.\.venv\Scripts\python.exe packaging\fetch_model.py base
.\packaging\build.ps1 -Model base -Zip
```

Measured on this project:

| build | installed | zipped |
|---|---|---|
| `-Zip` (model downloaded on first run) | 159 MB | 59 MB |
| `-Model base -Zip` (multilingual, offline) | 300 MB | 186 MB |
| `-Model small-int8 -WithVad` (**recommended**) | 436 MB | — |
| `-Model small` (the float16 weights the repo vendors) | 623 MB | — |

The runtime floor is ~159 MB and is almost entirely three native payloads:
`ctranslate2.dll` (57 MB, the inference engine), Qt (39 MB) and numpy's BLAS
(20 MB). Everything above that is the model, so **the model is the only real
size decision**.

### Quantize the model instead of shrinking it

Dropping from `small` to `base` costs real accuracy - on a hard word, `small`
hears "Kubernetes" where `base` hears "Cabernet". Quantizing costs nothing.
CTranslate2 already converts float16 weights to int8 while loading them on CPU,
so shipping int8 weights hands the CPU exactly the numbers it was going to
compute with anyway - at half the bytes.

```powershell
python -m venv build\convert-venv
.\build\convert-venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.\build\convert-venv\Scripts\python.exe -m pip install ctranslate2 transformers
.\build\convert-venv\Scripts\python.exe packaging\fetch_model.py small --int8 --name small-int8
.\packaging\build.ps1 -Model small-int8 -WithVad
```

`torch` is a build dependency only, which is why it goes in a throwaway venv -
nothing from it is shipped. `small` drops from 484 MB to 252 MB. Transcribing
four reference clips through both, on CPU int8 and on CUDA float16, the int8
weights produced output identical to float16 in every case.

Other flags:

| flag | effect |
|---|---|
| `-WithVad` | bundle `onnxruntime` (+45 MB) for the Silero VAD instead of the energy-based silence trim |
| `-Console` | keep a console window attached so `print()` output is visible |
| `-KeepAllQt` | ship every Qt DLL, including the 20 MB software OpenGL fallback |
| `-Zip` | also write `build\WhisperTranscriber.zip` |

Install a finished build for the current user - copied to
`%LOCALAPPDATA%\Programs` with a Start Menu shortcut, so it survives the
next `build.ps1 --clean` wiping the build folder:

```powershell
.\packaging\install.ps1 -Start
```

`-Remove` uninstalls it and leaves your settings and history alone.

The build ends by running `WhisperTranscriber.exe --selftest`, which constructs
the real widgets and (when a model is bundled) runs a transcription, so a build
that passes has proven its Qt, CTranslate2, tokenizers and numpy payloads all
load. You can run that by hand on any machine you deploy to.

### Start automatically on Windows

```powershell
.\packaging\install-autostart.ps1
```

Adds a per-user Startup shortcut that launches the app with `--background`, so
it comes up in the tray with no window. `-Remove` undoes it.

## Platform notes

- **Clipboard/paste**: uses Qt's clipboard + a simulated Ctrl+V, so no extra
  clipboard tool (`xclip`/`xsel`) is needed on Linux.
- **Global hotkey on Ubuntu**: this relies on X11 to listen for key events and
  to simulate the paste. **It will not work under a Wayland session**
  (Wayland blocks apps from seeing global input for security reasons) — at
  the login screen, choose **"Ubuntu on Xorg"** instead of the default
  "Ubuntu" session. Ubuntu 22.04/24.04 both still ship the Xorg option. The
  app detects a Wayland session at startup and says so, rather than starting
  up looking fine and then never responding to the hotkey.

  To make Xorg the permanent default (recommended — a kernel or NVIDIA driver
  update can flip GDM back to Wayland without warning, since GDM only forces
  Xorg while `nvidia_drm` reports `modeset != Y`):

  ```bash
  sudo sed -i 's/^#WaylandEnable=false/WaylandEnable=false/' /etc/gdm3/custom.conf
  ```

  then reboot. Verify afterwards with `echo $XDG_SESSION_TYPE` — it should
  print `x11`.
- **Tray icon on Ubuntu**: stock GNOME hides app tray icons. Install the
  **"AppIndicator and KStatusNotifierItem Support"** GNOME Shell extension
  (via `gnome-extensions-app` or extensions.gnome.org) to see it. If you'd
  rather skip that, you can run `main.py` and just leave the settings window
  open instead of relying on the tray.
- **GPU**: CUDA + float16 is used automatically if `ctranslate2` detects a
  CUDA device (confirmed working on an RTX 3050 on Windows); otherwise it
  falls back to CPU with int8 quantization, which is still real-time for the
  `small` model.

## Project layout

```
main.py                    entry point (Qt app bootstrap)
transcriber/
  config.py                config.json load/save
  audio.py                 mic recording (sounddevice)
  model.py                 faster-whisper wrapper, prefers vendored model
  engine.py                push-to-talk state machine (Qt signals)
  output.py                clipboard + simulated paste
  history.py                SQLite dictation history
  ui/
    main_window.py         status, hotkey, and history views
    tray.py                system tray icon
    indicator.py           floating dictation pill
    hotkey_dialog.py        "press any key" capture dialog
    theme.py                dark stylesheet + generated icon
  paths.py                 where to read resources / write state, frozen or not
packaging/
  build.ps1                one-command Windows build (see above)
  whisper.spec             PyInstaller spec: excludes, Qt pruning, model bundling
  rthook_stub_av.py        stands in for PyAV, which is imported but never used
  fetch_model.py           download a model into models/ so a build can bundle it
  install-autostart.ps1    Startup-folder shortcut for Windows
models/small/               vendored faster-whisper "small" model (~460 MB)
```
