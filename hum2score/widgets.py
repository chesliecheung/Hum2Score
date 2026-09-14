"""Qt widgets for pitch, numbered notation and staff previews."""

from __future__ import annotations

import math

import numpy as np
from PyQt6.QtCore import QLineF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

from .models import NoteEvent
from .notation import NATURAL_PCS, duration_name, numbered_name, pitch_name


class PitchPlot(QWidget):
    """Fast native-Qt pitch chart; avoids Matplotlib's cold-start font scan."""

    def __init__(self) -> None:
        super().__init__()
        self.times = np.array([], dtype=float)
        self.raw_midi = np.array([], dtype=float)
        self.smooth_midi = np.array([], dtype=float)
        self._highlight: tuple[float, float] | None = None
        self.setMinimumHeight(210)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def clear(self) -> None:
        self.times = np.array([], dtype=float)
        self.raw_midi = np.array([], dtype=float)
        self.smooth_midi = np.array([], dtype=float)
        self._highlight = None
        self.update()

    def set_track(
        self, times: np.ndarray, raw_midi: np.ndarray, smooth_midi: np.ndarray
    ) -> None:
        self.times = np.asarray(times, dtype=float)
        self.raw_midi = np.asarray(raw_midi, dtype=float)
        self.smooth_midi = np.asarray(smooth_midi, dtype=float)
        self._highlight = None
        self.update()

    def set_playback_index(self, index: int | None, events: list[NoteEvent]) -> None:
        self._highlight = None
        if index is not None and 0 <= index < len(events):
            item = events[index]
            self._highlight = (item.start, item.end)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        plot = QRectF(68, 18, max(10, self.width() - 92), max(10, self.height() - 58))
        if not self.times.size:
            painter.setPen(QColor("#98A1B2"))
            painter.setFont(QFont("Arial", 11))
            painter.drawText(plot, Qt.AlignmentFlag.AlignCenter, "录音完成后，音高轨迹会显示在这里")
            return

        finite = self.smooth_midi[np.isfinite(self.smooth_midi)]
        if not finite.size:
            return
        x_min, x_max = float(np.nanmin(self.times)), float(np.nanmax(self.times))
        if x_max <= x_min:
            x_max = x_min + 1.0
        y_min, y_max = math.floor(float(finite.min())) - 1, math.ceil(float(finite.max())) + 1
        if y_max <= y_min:
            y_max = y_min + 2

        def point(x: float, y: float):
            px = plot.left() + (x - x_min) / (x_max - x_min) * plot.width()
            py = plot.bottom() - (y - y_min) / (y_max - y_min) * plot.height()
            return px, py

        if self._highlight:
            hx1, _ = point(self._highlight[0], y_min)
            hx2, _ = point(self._highlight[1], y_min)
            painter.fillRect(QRectF(hx1, plot.top(), max(2, hx2 - hx1), plot.height()), QColor("#EAE7FF"))

        painter.setFont(QFont("Arial", 9))
        tick_step = max(1, math.ceil((y_max - y_min) / 9))
        for midi in range(y_min, y_max + 1, tick_step):
            _, py = point(x_min, midi)
            painter.setPen(QPen(QColor("#E8EBF1"), 1))
            painter.drawLine(QLineF(plot.left(), py, plot.right(), py))
            painter.setPen(QColor("#657084"))
            painter.drawText(QRectF(4, py - 9, 58, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, pitch_name(midi))
        painter.setPen(QPen(QColor("#CBD1DC"), 1))
        painter.drawLine(plot.bottomLeft(), plot.bottomRight())
        painter.drawLine(plot.topLeft(), plot.bottomLeft())

        def draw_curve(values: np.ndarray, color: str, width: float):
            path = QPainterPath()
            active = False
            for x, y in zip(self.times, values):
                if not np.isfinite(y):
                    active = False
                    continue
                px, py = point(float(x), float(y))
                if active:
                    path.lineTo(px, py)
                else:
                    path.moveTo(px, py)
                    active = True
            painter.setPen(QPen(QColor(color), width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

        draw_curve(self.raw_midi, "#B1B8C4", 1.0)
        draw_curve(self.smooth_midi, "#635BFF", 2.2)
        painter.setPen(QColor("#657084"))
        painter.drawText(QRectF(plot.left(), plot.bottom() + 12, plot.width(), 20), Qt.AlignmentFlag.AlignCenter, "时间 / 秒")
        painter.drawText(QRectF(plot.right() - 112, plot.top() + 4, 110, 18), Qt.AlignmentFlag.AlignRight, "灰：原始   紫：平滑")


class NumberedNotationWidget(QWidget):
    activated = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.events: list[NoteEvent] = []
        self.highlight_index: int | None = None
        self.setMinimumHeight(130)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit()
        super().mouseReleaseEvent(event)

    def set_events(self, events: list[NoteEvent]) -> None:
        self.events = list(events)
        rows = max(1, math.ceil(len(events) / 12))
        self.setMinimumHeight(35 + rows * 70)
        self.update()

    def set_highlight(self, index: int | None) -> None:
        self.highlight_index = index
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        painter.setPen(QColor("#273043"))
        painter.setFont(QFont("Arial", 10))
        painter.drawText(16, 24, "简谱预览  ·  C 大调唱名")
        if not self.events:
            painter.setPen(QColor("#8b95a5"))
            painter.drawText(16, 70, "录音解析后将在这里显示简谱")
            return
        cell_w, row_h = 72, 68
        columns = max(1, (self.width() - 24) // cell_w)
        for i, item in enumerate(self.events):
            x = 16 + (i % columns) * cell_w
            y = 47 + (i // columns) * row_h
            if i == self.highlight_index:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#EAE7FF"))
                painter.drawRoundedRect(QRectF(x, y - 4, cell_w - 8, 58), 9, 9)
            painter.setPen(QColor("#111827"))
            painter.setFont(QFont("Arial", 22, QFont.Weight.DemiBold))
            painter.drawText(QRectF(x, y, cell_w - 8, 30), Qt.AlignmentFlag.AlignCenter, numbered_name(item.midi))
            painter.setPen(QColor("#6b7280"))
            painter.setFont(QFont("Arial", 9))
            painter.drawText(QRectF(x, y + 30, cell_w - 8, 20), Qt.AlignmentFlag.AlignCenter, duration_name(item.quarter_length))


class StaffWidget(QWidget):
    """Dependency-free live staff preview of the music21-backed note model."""

    activated = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.events: list[NoteEvent] = []
        self.highlight_index: int | None = None
        self.setMinimumHeight(180)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit()
        super().mouseReleaseEvent(event)

    def set_events(self, events: list[NoteEvent]) -> None:
        self.events = list(events)
        systems = max(1, math.ceil(len(events) / 14))
        self.setMinimumHeight(35 + systems * 125)
        self.update()

    def set_highlight(self, index: int | None) -> None:
        self.highlight_index = index
        self.update()

    @staticmethod
    def _diatonic_index(midi: int) -> int:
        octave = midi // 12 - 1
        pc = midi % 12
        nearest = min(range(7), key=lambda i: abs(NATURAL_PCS[i] - pc))
        return octave * 7 + nearest

    def paintEvent(self, event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        painter.setPen(QColor("#273043"))
        painter.setFont(QFont("Arial", 10))
        painter.drawText(16, 22, "五线谱预览  ·  高音谱号")
        if not self.events:
            painter.setPen(QColor("#8b95a5"))
            painter.drawText(16, 80, "录音解析后将在这里显示五线谱")
            return

        left, right, spacing = 24, self.width() - 16, 12
        per_system = max(4, min(14, (right - left) // 54))
        pen = QPen(QColor("#333333"), 1)
        painter.setPen(pen)
        for system, offset in enumerate(range(0, len(self.events), per_system)):
            top = 47 + system * 125
            for line in range(5):
                y = top + line * spacing
                painter.drawLine(left, y, right, y)
            painter.setFont(QFont("Times New Roman", 34))
            painter.drawText(left + 2, top + 43, "𝄞")
            available = max(1, min(per_system, len(self.events) - offset))
            step = (right - left - 70) / available
            for local, item in enumerate(self.events[offset : offset + per_system]):
                x = left + 68 + local * step
                # Bottom line E4 has diatonic index 4*7+2 = 30.
                diatonic = self._diatonic_index(item.midi)
                y = top + 4 * spacing - (diatonic - 30) * (spacing / 2)
                absolute_index = offset + local
                if absolute_index == self.highlight_index:
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor("#EAE7FF"))
                    painter.drawRoundedRect(QRectF(x - 18, top - 12, 36, 92), 9, 9)
                painter.setPen(QPen(QColor("#111827"), 1))
                painter.save()
                painter.translate(x, y)
                painter.rotate(-18)
                painter.setBrush(QColor("#111827"))
                painter.drawEllipse(QRectF(-6, -4, 12, 8))
                painter.restore()
                if item.quarter_length < 4:
                    painter.drawLine(int(x + 5), int(y), int(x + 5), int(y - 31))
                if y > top + 4 * spacing:
                    ledger = top + 5 * spacing
                    while ledger <= y + 2:
                        painter.drawLine(int(x - 10), int(ledger), int(x + 10), int(ledger))
                        ledger += spacing
                if y < top:
                    ledger = top - spacing
                    while ledger >= y - 2:
                        painter.drawLine(int(x - 10), int(ledger), int(x + 10), int(ledger))
                        ledger -= spacing
                painter.setFont(QFont("Arial", 8))
                painter.drawText(QRectF(x - 25, top + 65, 50, 18), Qt.AlignmentFlag.AlignCenter, pitch_name(item.midi))
