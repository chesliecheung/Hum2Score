"""Shared data models."""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class NoteEvent:
    """One stable, quantized monophonic note."""

    midi: int
    start: float
    duration: float
    confidence: float = 1.0
    quarter_length: float = 1.0

    @property
    def end(self) -> float:
        return self.start + self.duration

    def with_midi(self, midi: int) -> "NoteEvent":
        return replace(self, midi=max(0, min(127, int(midi))))

