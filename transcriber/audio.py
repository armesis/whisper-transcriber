"""Microphone recording, active only between start() and stop()."""
import numpy as np
import sounddevice as sd


class Recorder:
    def __init__(self, sample_rate: int):
        self.sample_rate = sample_rate
        self._chunks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None

    def _callback(self, indata, frames, time_info, status):
        self._chunks.append(indata.copy())

    def start(self) -> None:
        self._chunks = []
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        if self._stream is None:
            return np.zeros(0, dtype=np.float32)
        self._stream.stop()
        self._stream.close()
        self._stream = None
        if not self._chunks:
            return np.zeros(0, dtype=np.float32)
        audio = np.concatenate(self._chunks, axis=0).flatten()
        self._chunks = []
        return audio

    def seconds_recorded(self) -> float:
        total_frames = sum(chunk.shape[0] for chunk in self._chunks)
        return total_frames / self.sample_rate
