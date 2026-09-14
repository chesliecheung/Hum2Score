import unittest

import numpy as np

from hum2score.notation import numbered_name, octave_for_midi
from hum2score.pitch import PitchTrack
from hum2score.quantizer import MelodyQuantizer, QuantizerConfig


class QuantizerTests(unittest.TestCase):
    def make_track(self, pitches):
        midi = np.asarray(pitches, dtype=float)
        frequency = 440.0 * 2.0 ** ((midi - 69.0) / 12.0)
        return PitchTrack(np.arange(len(midi)) * 0.01, frequency, np.ones(len(midi)))

    def test_vibrato_is_one_note(self):
        t = np.arange(100)
        track = self.make_track(60 + 0.25 * np.sin(t / 3))
        _, notes = MelodyQuantizer().quantize(track)
        self.assertEqual([n.midi for n in notes], [60])

    def test_large_stable_change_splits_notes(self):
        track = self.make_track(np.r_[np.full(50, 60), np.full(50, 62)])
        _, notes = MelodyQuantizer().quantize(track)
        self.assertEqual([n.midi for n in notes], [60, 62])

    def test_short_glitch_does_not_create_note(self):
        track = self.make_track(np.r_[np.full(40, 60), np.full(3, 67), np.full(40, 60)])
        _, notes = MelodyQuantizer(QuantizerConfig(min_note_duration=0.1)).quantize(track)
        self.assertNotIn(67, [n.midi for n in notes])

    def test_numbered_octave_marks(self):
        self.assertEqual(octave_for_midi(60), 4)
        self.assertEqual(numbered_name(60), "1")
        self.assertIn("̇", numbered_name(72))
        self.assertIn("̣", numbered_name(48))


if __name__ == "__main__":
    unittest.main()

