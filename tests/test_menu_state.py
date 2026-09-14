import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from hum2score.main_window import MainWindow
from hum2score.models import NoteEvent


class MenuStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_refresh_updates_tray_actions(self):
        window = MainWindow()
        self.assertFalse(window.tray_play_action.isEnabled())
        window.events = [NoteEvent(60, 0.0, 0.5)]
        window.refresh_results()
        self.assertTrue(window.play_all_button.isEnabled())
        self.assertTrue(window.tray_play_action.isEnabled())
        self.assertTrue(window.tray_save_action.isEnabled())
        window.tray.hide()
        window._quitting = True
        window.close()


if __name__ == "__main__":
    unittest.main()
