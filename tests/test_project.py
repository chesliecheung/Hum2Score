import tempfile
import unittest
from pathlib import Path

import numpy as np

from hum2score.models import NoteEvent
from hum2score.pitch import PitchTrack
from hum2score.project import load_project, save_project


class ProjectTests(unittest.TestCase):
    def test_round_trip_keeps_audio_notes_and_pitch(self):
        events = [NoteEvent(60, 0.1, 0.4, 0.9, 1.0), NoteEvent(64, 0.6, 0.8, 0.8, 2.0)]
        audio = np.linspace(-0.2, 0.2, 160, dtype=np.float32)
        track = PitchTrack(np.array([0.0, 0.1]), np.array([261.6, 329.6]), np.array([0.9, 0.8]))
        smooth = np.array([60.0, 64.0])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.hum2score"
            save_project(path, events, audio, 16000, track, smooth)
            loaded_events, loaded_audio, rate, loaded_track, loaded_smooth = load_project(path)
        self.assertEqual(loaded_events, events)
        self.assertEqual(rate, 16000)
        np.testing.assert_allclose(loaded_audio, audio)
        np.testing.assert_allclose(loaded_track.frequencies, track.frequencies)
        np.testing.assert_allclose(loaded_smooth, smooth)


if __name__ == "__main__":
    unittest.main()
