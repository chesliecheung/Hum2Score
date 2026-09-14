import tempfile
import unittest
from pathlib import Path

from music21 import converter

from hum2score.models import NoteEvent
from hum2score.notation import export_midi


class MidiExportTests(unittest.TestCase):
    def test_midi_preserves_edited_start_time(self):
        events = [
            NoteEvent(60, 0.0, 0.4, 1.0, 1.0),
            NoteEvent(64, 2.0, 0.4, 1.0, 1.0),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "timing.mid"
            export_midi(events, path)
            score = converter.parse(path)
            offsets = [float(item.offset) for item in score.recurse().notes]
        self.assertEqual(offsets, [0.0, 3.0])


if __name__ == "__main__":
    unittest.main()
