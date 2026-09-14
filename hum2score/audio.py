"""Microphone recording based on sounddevice."""

from __future__ import annotations

import threading

import numpy as np
import sounddevice as sd
from PyQt6.QtCore import QObject, pyqtSignal


class AudioRecorder(QObject):
    """Capture mono float32 samples without blocking the Qt event loop."""

    level_changed = pyqtSignal(float)
    error = pyqtSignal(str)

    def __init__(self, sample_rate: int = 16000) -> None:
        super().__init__()
        self.sample_rate = sample_rate
        self._chunks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        if self.is_recording:
            return
        with self._lock:
            self._chunks.clear()
        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=1024,
                callback=self._callback,
            )
            self._stream.start()
        except Exception:
            self._stream = None
            raise

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ANN001
        if status:
            self.error.emit(str(status))
        chunk = np.asarray(indata[:, 0], dtype=np.float32).copy()
        with self._lock:
            self._chunks.append(chunk)
        rms = float(np.sqrt(np.mean(chunk * chunk))) if len(chunk) else 0.0
        self.level_changed.emit(min(1.0, rms * 12.0))

    def stop(self) -> np.ndarray:
        stream, self._stream = self._stream, None
        if stream is not None:
            stream.stop()
            stream.close()
        with self._lock:
            if not self._chunks:
                return np.empty(0, dtype=np.float32)
            return np.concatenate(self._chunks).astype(np.float32, copy=False)

