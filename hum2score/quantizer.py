"""Convert a noisy continuous pitch track into stable discrete notes."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import median_filter

from .models import NoteEvent
from .pitch import PitchTrack


@dataclass
class QuantizerConfig:
    change_threshold: float = 0.70  # semitones
    min_note_duration: float = 0.12
    max_gap_duration: float = 0.08
    confirmation_duration: float = 0.05


class MelodyQuantizer:
    """Smooth, segment and quantize a monophonic vocal pitch track.

    The state machine uses hysteresis: a candidate pitch must remain sufficiently
    far from the current note for several frames before a split is accepted. This
    suppresses vibrato and one-frame pitch glitches.
    """

    def __init__(self, config: QuantizerConfig | None = None) -> None:
        self.config = config or QuantizerConfig()

    def quantize(self, track: PitchTrack) -> tuple[np.ndarray, list[NoteEvent]]:
        times = np.asarray(track.times, dtype=float)
        midi = track.midi
        conf = np.asarray(track.confidences, dtype=float)
        if len(times) < 2:
            return midi, []
        frame_dt = float(np.median(np.diff(times)))
        smooth = self._smooth_and_bridge(midi, frame_dt)
        notes = self._segment(times, smooth, conf, frame_dt)
        notes = self._merge_short(notes)
        return smooth, self._estimate_rhythm(notes)

    def _smooth_and_bridge(self, midi: np.ndarray, frame_dt: float) -> np.ndarray:
        result = np.asarray(midi, dtype=float).copy()
        valid = np.isfinite(result)
        # Median filtering only on filled values prevents NaNs from spreading.
        if valid.any():
            indices = np.arange(len(result))
            filled = np.interp(indices, indices[valid], result[valid])
            filled = median_filter(filled, size=5, mode="nearest")
            result[valid] = filled[valid]

        max_gap = max(1, round(self.config.max_gap_duration / frame_dt))
        i = 0
        while i < len(result):
            if np.isfinite(result[i]):
                i += 1
                continue
            start = i
            while i < len(result) and not np.isfinite(result[i]):
                i += 1
            if (
                start > 0
                and i < len(result)
                and i - start <= max_gap
                and abs(result[start - 1] - result[i]) < 1.0
            ):
                result[start:i] = np.linspace(
                    result[start - 1], result[i], i - start + 2
                )[1:-1]
        return result

    def _segment(
        self,
        times: np.ndarray,
        midi: np.ndarray,
        confidence: np.ndarray,
        frame_dt: float,
    ) -> list[NoteEvent]:
        notes: list[NoteEvent] = []
        confirm_frames = max(2, round(self.config.confirmation_duration / frame_dt))
        i = 0
        while i < len(midi):
            if not np.isfinite(midi[i]):
                i += 1
                continue
            start = i
            stable_values = [midi[i]]
            center = midi[i]
            candidate_start: int | None = None
            i += 1
            while i < len(midi) and np.isfinite(midi[i]):
                distance = abs(midi[i] - center)
                if distance >= self.config.change_threshold:
                    candidate_start = candidate_start if candidate_start is not None else i
                    if i - candidate_start + 1 >= confirm_frames:
                        i = candidate_start
                        break
                else:
                    candidate_start = None
                    stable_values.append(midi[i])
                    center = float(np.median(stable_values[-25:]))
                i += 1
            end = i
            if end <= start:
                i = start + 1
                continue
            duration = (times[end - 1] - times[start]) + frame_dt
            segment_values = midi[start:end]
            segment_conf = confidence[start:end]
            valid = np.isfinite(segment_values)
            if duration >= self.config.min_note_duration * 0.45 and valid.any():
                pitch = int(np.rint(np.median(segment_values[valid])))
                notes.append(
                    NoteEvent(
                        midi=pitch,
                        start=float(times[start]),
                        duration=float(duration),
                        confidence=float(np.mean(segment_conf[valid])),
                    )
                )
            if i == end and i < len(midi) and not np.isfinite(midi[i]):
                i += 1
        return notes

    def _merge_short(self, notes: list[NoteEvent]) -> list[NoteEvent]:
        if not notes:
            return []
        result: list[NoteEvent] = []
        for note in notes:
            # Merge repeated adjacent pitches across tiny gaps.
            if result and note.midi == result[-1].midi and note.start - result[-1].end < 0.12:
                prev = result.pop()
                total_end = note.end
                result.append(
                    NoteEvent(
                        prev.midi,
                        prev.start,
                        total_end - prev.start,
                        (prev.confidence + note.confidence) / 2,
                    )
                )
                continue
            if note.duration < self.config.min_note_duration:
                if result and abs(note.midi - result[-1].midi) <= 1:
                    prev = result.pop()
                    result.append(
                        NoteEvent(
                            prev.midi,
                            prev.start,
                            note.end - prev.start,
                            (prev.confidence + note.confidence) / 2,
                        )
                    )
                continue
            result.append(note)
        return result

    @staticmethod
    def _estimate_rhythm(notes: list[NoteEvent]) -> list[NoteEvent]:
        if not notes:
            return []
        durations = np.array([n.duration for n in notes])
        # A robust pulse estimate: the lower-middle duration usually corresponds
        # to one beat in short hummed phrases.
        beat = float(np.percentile(durations, 40))
        beat = float(np.clip(beat, 0.18, 1.2))
        allowed = np.array([0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0])
        output: list[NoteEvent] = []
        for note in notes:
            ratio = note.duration / beat
            ql = float(allowed[np.argmin(abs(allowed - ratio))])
            output.append(
                NoteEvent(note.midi, note.start, note.duration, note.confidence, ql)
            )
        return output

