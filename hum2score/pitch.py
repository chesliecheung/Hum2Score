"""CREPE-based continuous pitch extraction."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class PitchTrack:
    times: np.ndarray
    frequencies: np.ndarray
    confidences: np.ndarray

    @property
    def midi(self) -> np.ndarray:
        result = np.full_like(self.frequencies, np.nan, dtype=float)
        valid = np.isfinite(self.frequencies) & (self.frequencies > 0)
        result[valid] = 69.0 + 12.0 * np.log2(self.frequencies[valid] / 440.0)
        return result


class CrepePitchDetector:
    """Lazy-load CREPE and return a confidence-filtered pitch track."""

    target_rate = 16000

    def analyze(
        self,
        audio: np.ndarray,
        sample_rate: int,
        confidence_threshold: float = 0.55,
    ) -> PitchTrack:
        if audio.size < sample_rate * 0.15:
            raise ValueError("录音太短，请至少哼唱 0.15 秒。")

        # CREPE expects mono audio sampled at 16 kHz.
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if sample_rate != self.target_rate:
            from math import gcd
            from scipy.signal import resample_poly

            divisor = gcd(sample_rate, self.target_rate)
            samples = resample_poly(
                samples, self.target_rate // divisor, sample_rate // divisor
            ).astype(np.float32)

        peak = float(np.max(np.abs(samples)))
        if peak < 1e-4:
            raise ValueError("没有检测到可用声音，请检查麦克风输入。")
        samples = samples / max(peak, 1.0)

        try:
            import crepe
        except ImportError as exc:
            raise RuntimeError(
                "未安装 CREPE/TensorFlow。请执行 pip install -r requirements.txt"
            ) from exc

        time, frequency, confidence, _ = crepe.predict(
            samples,
            self.target_rate,
            model_capacity="small",
            viterbi=True,
            step_size=10,
            verbose=0,
        )
        frequency = np.asarray(frequency, dtype=float)
        confidence = np.asarray(confidence, dtype=float)

        # Humming is generally in this range. Outliers and low-confidence frames
        # become gaps instead of bogus notes.
        voiced = (
            (confidence >= confidence_threshold)
            & (frequency >= 65.0)
            & (frequency <= 1500.0)
        )
        frequency[~voiced] = np.nan
        return PitchTrack(np.asarray(time), frequency, confidence)
