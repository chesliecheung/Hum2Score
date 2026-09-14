"""Clear, discoverable note editing dialog."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from .models import NoteEvent
from .notation import PITCH_CLASSES, duration_name, octave_for_midi


class NoteEditorDialog(QDialog):
    def __init__(self, event: NoteEvent, title: str, parent=None) -> None:
        super().__init__(parent)
        self.original = event
        self.setWindowTitle(title)
        self.setMinimumWidth(390)
        layout = QVBoxLayout(self)
        heading = QLabel(title)
        heading.setObjectName("viewerTitle")
        hint = QLabel("修改后，试听、整段播放、乐谱与导出会立即同步。")
        hint.setObjectName("muted")
        layout.addWidget(heading)
        layout.addWidget(hint)
        form = QFormLayout()
        form.setSpacing(12)
        self.pitch = QComboBox()
        self.pitch.addItems(PITCH_CLASSES)
        self.pitch.setCurrentIndex(event.midi % 12)
        self.octave = QSpinBox()
        self.octave.setRange(1, 8)
        self.octave.setValue(octave_for_midi(event.midi))
        self.start = QDoubleSpinBox()
        self.start.setRange(0, 3600)
        self.start.setDecimals(3)
        self.start.setSuffix(" 秒")
        self.start.setValue(event.start)
        self.duration = QDoubleSpinBox()
        self.duration.setRange(0.05, 30)
        self.duration.setDecimals(3)
        self.duration.setSuffix(" 秒")
        self.duration.setValue(event.duration)
        self.rhythm = QComboBox()
        self.rhythm_values = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0)
        for value in self.rhythm_values:
            self.rhythm.addItem(f"{duration_name(value)} · {value:g} 拍", value)
        self.rhythm.setCurrentIndex(
            min(range(len(self.rhythm_values)), key=lambda i: abs(self.rhythm_values[i] - event.quarter_length))
        )
        form.addRow("音高", self.pitch)
        form.addRow("八度", self.octave)
        form.addRow("开始位置", self.start)
        form.addRow("实际时长", self.duration)
        form.addRow("乐谱时值", self.rhythm)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def note_event(self) -> NoteEvent:
        midi = (self.octave.value() + 1) * 12 + self.pitch.currentIndex()
        return NoteEvent(
            midi=midi,
            start=self.start.value(),
            duration=self.duration.value(),
            confidence=self.original.confidence,
            quarter_length=float(self.rhythm.currentData()),
        )

