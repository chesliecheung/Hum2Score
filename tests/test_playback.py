import unittest
from unittest.mock import patch

import numpy as np
from PyQt6.QtCore import QCoreApplication

from hum2score.models import NoteEvent
from hum2score.playback import MelodyPlayer


class PlaybackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_tone_has_expected_length_and_fades(self):
        player = MelodyPlayer(sample_rate=8000)
        tone = player._tone(69, 0.5)
        self.assertEqual(len(tone), 4000)
        self.assertEqual(tone.dtype, np.float32)
        self.assertLess(abs(float(tone[0])), 1e-5)
        self.assertLess(abs(float(tone[-1])), 1e-5)
        self.assertGreater(float(np.max(np.abs(tone))), 0.1)

    def test_full_preview_respects_edited_start_times(self):
        events = [
            NoteEvent(60, 0.0, 0.4),
            NoteEvent(64, 2.0, 0.4),
        ]
        captured = {}
        with patch(
            "hum2score.playback.sd.play",
            lambda audio, rate, blocking=False: captured.update(audio=audio, rate=rate),
        ), patch("hum2score.playback.sd.stop"):
            player = MelodyPlayer(sample_rate=1000)
            self.assertTrue(player.play(events, respect_timeline=True))
            player.stop()
        self.assertEqual(len(captured["audio"]), 2400)
        self.assertGreater(float(np.max(np.abs(captured["audio"][2000:]))), 0.1)


if __name__ == "__main__":
    unittest.main()
