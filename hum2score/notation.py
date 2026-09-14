"""Music naming, numbered notation and music21 export helpers."""

from __future__ import annotations

from pathlib import Path

from .models import NoteEvent


PITCH_CLASSES = ("C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B")
SOLFEGE = ("do", "do♯", "re", "re♯", "mi", "fa", "fa♯", "sol", "sol♯", "la", "la♯", "si")
NUMBERED = ("1", "1♯", "2", "2♯", "3", "4", "4♯", "5", "5♯", "6", "6♯", "7")
NATURAL_PCS = (0, 2, 4, 5, 7, 9, 11)
DEFAULT_BPM = 90


def octave_for_midi(midi: int) -> int:
    return midi // 12 - 1


def pitch_name(midi: int) -> str:
    return f"{PITCH_CLASSES[midi % 12]}{octave_for_midi(midi)}"


def solfege_name(midi: int) -> str:
    return SOLFEGE[midi % 12]


def numbered_name(midi: int) -> str:
    """Return numbered notation with dots above/below relative to octave 4."""
    number = NUMBERED[midi % 12]
    delta = octave_for_midi(midi) - 4
    if delta > 0:
        return number + "".join("̇" for _ in range(delta))
    if delta < 0:
        return number + "".join("̣" for _ in range(-delta))
    return number


def duration_name(quarter_length: float) -> str:
    labels = {
        0.25: "十六分",
        0.5: "八分",
        0.75: "附点八分",
        1.0: "四分",
        1.5: "附点四分",
        2.0: "二分",
        3.0: "附点二分",
        4.0: "全音符",
    }
    return labels.get(float(quarter_length), f"{quarter_length:g} 拍")


def midi_from_name(name: str, octave: int) -> int:
    normalized = name.replace("♯", "#")
    pc_names = [value.replace("♯", "#") for value in PITCH_CLASSES]
    return max(0, min(127, (octave + 1) * 12 + pc_names.index(normalized)))


def build_score(events: list[NoteEvent]):
    # music21 is intentionally loaded only when MIDI is exported. Importing it
    # during application launch noticeably delays a frozen macOS app.
    from music21 import instrument, metadata, note, stream, tempo

    score = stream.Score()
    score.metadata = metadata.Metadata(title="Hum2Score Melody")
    part = stream.Part()
    part.insert(0, instrument.Instrument(instrumentName="Voice"))
    part.insert(0, tempo.MetronomeMark(number=DEFAULT_BPM))
    for event in events:
        item = note.Note()
        item.pitch.midi = event.midi
        item.quarterLength = event.quarter_length
        # start is stored in seconds. At DEFAULT_BPM, convert seconds to
        # quarter-note offsets so manual timeline edits survive MIDI export.
        part.insert(max(0.0, event.start) * DEFAULT_BPM / 60.0, item)
    score.append(part)
    return score


def export_midi(events: list[NoteEvent], path: str | Path) -> None:
    build_score(events).write("midi", fp=str(path))


def export_numbered_text(events: list[NoteEvent], path: str | Path) -> None:
    sequence = "  ".join(numbered_name(event.midi) for event in events)
    details = ["Hum2Score 简谱", "", sequence, "", "序号\t简谱\t唱名\t音名\t时长(秒)\t估算时值"]
    for index, event in enumerate(events, 1):
        details.append(
            f"{index}\t{numbered_name(event.midi)}\t{solfege_name(event.midi)}\t"
            f"{pitch_name(event.midi)}\t{event.duration:.2f}\t{duration_name(event.quarter_length)}"
        )
    Path(path).write_text("\n".join(details) + "\n", encoding="utf-8")
