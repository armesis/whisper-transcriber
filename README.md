# whisper-transcriber

Push-to-talk dictation for your desktop. Hold a hotkey, speak, release — your
speech is transcribed locally with
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) and pasted at your
cursor wherever you're typing.

Runs fully offline (the `small` model is vendored in `models/`, no download or
API calls needed) and uses your GPU automatically when one is available. Works
on Windows and Ubuntu/Linux from the same codebase.

It has a focused dark-themed UI, searchable history, and an animated companion
that shows live microphone levels while listening, waits during transcription,
and confirms when the text has been pasted.

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
speak, then release. The floating companion shows **Listening** with a live
waveform, **Transcribing**, and **Pasted**. The text is inserted automatically
at the cursor. Accidental short taps are ignored and the indicator closes
without getting stuck.

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
whether to paste automatically) still live in `config.json`, created next to
`main.py` on first run:

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
    main_window.py         focused status, hotkey, and history views
    tray.py                system tray icon
    indicator.py           animated companion + dictation state bubble
    hotkey_dialog.py        "press any key" capture dialog
    theme.py                dark stylesheet + generated icon
models/small/               vendored faster-whisper "small" model (~460 MB)
assets/                     companion artwork used by the UI
```
