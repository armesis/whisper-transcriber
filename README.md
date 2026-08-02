# whisper-transcriber

Push-to-talk dictation for your desktop. Hold a hotkey, speak, release — your
speech is transcribed locally with
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) and pasted at your
cursor wherever you're typing.

Runs fully offline (the `small` model is vendored in `models/`, no download or
API calls needed) and uses your GPU automatically when one is available. Works
on Windows and Ubuntu/Linux from the same codebase.

It has a small always-on dark-themed UI (tray icon, floating "Listening..."
indicator, hotkey picker, and searchable history) instead of hand-editing a
config file — inspired by dictation tools like Wispr Flow, though this is an
independent build, not a copy of their (closed-source) interface.

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

```bash
python main.py
```

A tray icon appears (a purple mic in a circle). Click it to open the settings
window, where you can:

- **Hotkey tab** — click the key button and hold whatever you want your new
  push-to-talk hotkey to be; it can be a single key or a combo (e.g. hold
  Ctrl then Win) — release any one of them to finish capturing (default:
  **F9**). Releasing any key in the combo while dictating stops the recording.
- **History tab** — every transcript is saved locally (`history.db`, SQLite);
  search it, double-click an entry to copy it back to the clipboard, delete
  entries, or clear everything.

To dictate: hold the hotkey, speak, release — a small pill appears at the
bottom of your screen ("Listening..." → "Transcribing...") and the text is
pasted into whatever field has focus.

Closing the settings window just hides it — the app keeps running in the
tray. Quit from the tray menu.

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
  "Ubuntu" session. Ubuntu 22.04/24.04 both still ship the Xorg option.
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
    main_window.py         settings window (Hotkey + History tabs)
    tray.py                system tray icon
    indicator.py            floating "Listening..." pill
    hotkey_dialog.py        "press any key" capture dialog
    theme.py                dark stylesheet + generated icon
models/small/               vendored faster-whisper "small" model (~460 MB)
```
