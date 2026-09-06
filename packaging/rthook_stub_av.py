"""Satisfy faster-whisper's `import av` without shipping PyAV (~66 MB).

faster_whisper.audio imports PyAV at module scope purely to decode media files
off disk. This app only ever hands it a numpy array recorded from the
microphone, so every real PyAV call site is dead code here - but the import
still has to succeed. Register a stand-in that raises only if something
actually tries to decode a file.
"""
import sys
import types

_MESSAGE = (
    "This build does not include PyAV, so it cannot decode audio files. "
    "It transcribes microphone input only."
)


def _unavailable(*_args, **_kwargs):
    raise RuntimeError(_MESSAGE)


if "av" not in sys.modules:
    av = types.ModuleType("av")

    error = types.ModuleType("av.error")

    class InvalidDataError(Exception):
        pass

    error.InvalidDataError = InvalidDataError
    error.FFmpegError = Exception

    resampler = types.ModuleType("av.audio.resampler")
    resampler.AudioResampler = _unavailable
    fifo = types.ModuleType("av.audio.fifo")
    fifo.AudioFifo = _unavailable

    audio = types.ModuleType("av.audio")
    audio.resampler = resampler
    audio.fifo = fifo

    av.open = _unavailable
    av.error = error
    av.audio = audio
    av.__version__ = "0.0.0+stub"

    sys.modules.update(
        {
            "av": av,
            "av.error": error,
            "av.audio": audio,
            "av.audio.resampler": resampler,
            "av.audio.fifo": fifo,
        }
    )
