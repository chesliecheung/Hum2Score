"""Hum2Score application entry point."""

import os
import sys
from pathlib import Path

# Reduce TensorFlow's very noisy startup logging before CREPE is imported.
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from hum2score.main_window import MainWindow


def self_test() -> int:
    """Exercise the frozen CREPE model without opening a microphone or window."""
    import numpy as np

    from hum2score.pitch import CrepePitchDetector

    sample_rate = 16000
    time = np.arange(sample_rate, dtype=np.float32) / sample_rate
    envelope = np.minimum(1, time * 10) * np.minimum(1, (1 - time) * 10)
    audio = (0.25 * np.sin(2 * np.pi * 440 * time) * envelope).astype(np.float32)
    track = CrepePitchDetector().analyze(audio, sample_rate, 0.35)
    valid = track.frequencies[np.isfinite(track.frequencies)]
    median = float(np.median(valid)) if valid.size else 0.0
    if valid.size < 40 or not 430.0 < median < 450.0:
        print(f"Hum2Score self-test failed: voiced={valid.size}, median={median:.2f}")
        return 1
    print(f"Hum2Score self-test OK: voiced={valid.size}, median={median:.2f} Hz")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    app = QApplication(sys.argv)
    app.setApplicationName("Hum2Score")
    app.setOrganizationName("Hum2Score")
    app.setQuitOnLastWindowClosed(False)
    resource_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    icon_path = resource_root / "assets/hum2score-icon.png"
    if icon_path.exists() and sys.platform != "darwin":
        # Explicitly sets the Dock icon as well as individual window icons.
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
