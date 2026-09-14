"""Lightweight note preview synthesis through sounddevice."""

from __future__ import annotations

import numpy as np
import sounddevice as sd
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .models import NoteEvent


class MelodyPlayer(QObject):
    """Synthesize a soft, voice-like tone for one note or a full melody."""

    note_started = pyqtSignal(int)
    finished = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, sample_rate: int = 44100) -> None:
        super().__init__()
        self.sample_rate = sample_rate
        self._generation = 0
        self._playing = False

    @property
    def is_playing(self) -> bool:
        return self._playing

    def play(
        self,
        events: list[NoteEvent],
        source_rows: list[int] | None = None,
        respect_timeline: bool = False,
    ) -> bool:
        self.stop(emit_finished=False)
        if not events:
            return False
        rows = source_rows or list(range(len(events)))
        offsets_ms: list[int] = []
        if respect_timeline:
            timeline_end = max(max(0.0, event.start) + max(0.05, event.duration) for event in events)
            audio = np.zeros(max(1, round(timeline_end * self.sample_rate)), dtype=np.float32)
            for event in events:
                start = max(0.0, float(event.start))
                tone = self._tone(event.midi, float(np.clip(event.duration, 0.05, 30.0)))
                begin = round(start * self.sample_rate)
                end = min(len(audio), begin + len(tone))
                audio[begin:end] += tone[: end - begin]
                offsets_ms.append(round(start * 1000))
            peak = float(np.max(np.abs(audio)))
            if peak > 0.95:
                audio *= 0.95 / peak
            elapsed = timeline_end
        else:
            pieces: list[np.ndarray] = []
            elapsed = 0.0
            gap = 0.035
            for event in events:
                duration = float(np.clip(event.duration, 0.05, 30.0))
                offsets_ms.append(round(elapsed * 1000))
                pieces.append(self._tone(event.midi, duration))
                pieces.append(np.zeros(round(gap * self.sample_rate), dtype=np.float32))
                elapsed += duration + gap
            audio = np.concatenate(pieces)
        self._generation += 1
        generation = self._generation
        try:
            sd.play(audio, self.sample_rate, blocking=False)
        except Exception as exc:
            self.failed.emit(str(exc))
            return False
        self._playing = True
        for offset, row in zip(offsets_ms, rows):
            QTimer.singleShot(offset, lambda r=row, g=generation: self._announce(r, g))
        QTimer.singleShot(round(elapsed * 1000), lambda g=generation: self._finish(g))
        return True

    def play_audio(
        self,
        audio: np.ndarray,
        sample_rate: int,
        events: list[NoteEvent],
    ) -> bool:
        """Play the captured/imported audio and announce notes on its timeline."""
        self.stop(emit_finished=False)
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return False
        self._generation += 1
        generation = self._generation
        try:
            sd.play(samples, int(sample_rate), blocking=False)
        except Exception as exc:
            self.failed.emit(str(exc))
            return False
        self._playing = True
        for row, event in enumerate(events):
            QTimer.singleShot(
                max(0, round(event.start * 1000)),
                lambda r=row, g=generation: self._announce(r, g),
            )
        duration_ms = round(samples.size / sample_rate * 1000)
        QTimer.singleShot(duration_ms, lambda g=generation: self._finish(g))
        return True

    def stop(self, emit_finished: bool = True) -> None:
        self._generation += 1
        was_playing, self._playing = self._playing, False
        sd.stop()
        if emit_finished and was_playing:
            self.finished.emit()

    def _announce(self, row: int, generation: int) -> None:
        if self._playing and generation == self._generation:
            self.note_started.emit(row)

    def _finish(self, generation: int) -> None:
        if self._playing and generation == self._generation:
            self._playing = False
            self.finished.emit()

    def _tone(self, midi: int, duration: float) -> np.ndarray:
        count = max(1, round(duration * self.sample_rate))
        time = np.arange(count, dtype=np.float32) / self.sample_rate
        frequency = 440.0 * 2.0 ** ((midi - 69) / 12.0)
        # A quiet fundamental plus two harmonics sounds warmer than a test sine.
        wave = (
            0.70 * np.sin(2 * np.pi * frequency * time)
            + 0.20 * np.sin(2 * np.pi * frequency * 2 * time)
            + 0.10 * np.sin(2 * np.pi * frequency * 3 * time)
        )
        attack = min(round(0.018 * self.sample_rate), count // 2)
        release = min(round(0.055 * self.sample_rate), count // 2)
        envelope = np.ones(count, dtype=np.float32)
        if attack:
            envelope[:attack] = np.linspace(0.0, 1.0, attack)
        if release:
            envelope[-release:] = np.linspace(1.0, 0.0, release)
        return (0.20 * wave * envelope).astype(np.float32)


class Metronome(QObject):
    beat = pyqtSignal()

    def __init__(self, sample_rate: int = 44100) -> None:
        super().__init__()
        self.sample_rate = sample_rate
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._click)
        self._click_audio = self._make_click()

    @property
    def is_active(self) -> bool:
        return self.timer.isActive()

    def start(self, bpm: int) -> None:
        self.timer.setInterval(round(60000 / max(30, min(240, bpm))))
        self._click()
        self.timer.start()

    def stop(self) -> None:
        self.timer.stop()

    def _click(self) -> None:
        try:
            sd.play(self._click_audio, self.sample_rate, blocking=False)
            self.beat.emit()
        except Exception:
            self.stop()

    def _make_click(self) -> np.ndarray:
        duration = 0.045
        time = np.arange(round(duration * self.sample_rate), dtype=np.float32) / self.sample_rate
        envelope = np.exp(-time * 75)
        return (0.28 * np.sin(2 * np.pi * 1200 * time) * envelope).astype(np.float32)
