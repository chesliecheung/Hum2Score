import tempfile
import unittest
import re
from pathlib import Path

from hum2score.models import NoteEvent
from hum2score.pdf_export import export_score_pdf


class PdfExportTests(unittest.TestCase):
    def test_exports_a_nonempty_pdf(self):
        events = [
            NoteEvent(60, 0.0, 0.5, 0.95, 1.0),
            NoteEvent(64, 0.5, 0.5, 0.95, 1.0),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "score.pdf"
            export_score_pdf(events, path)
            self.assertTrue(path.read_bytes().startswith(b"%PDF"))
            self.assertGreater(path.stat().st_size, 1_000)

    def test_long_score_is_paginated(self):
        events = [NoteEvent(60 + index % 12, index * 0.5, 0.4) for index in range(80)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "long-score.pdf"
            export_score_pdf(events, path)
            page_count = len(re.findall(rb"/Type\s*/Page\b", path.read_bytes()))
        self.assertEqual(page_count, 4)


if __name__ == "__main__":
    unittest.main()
