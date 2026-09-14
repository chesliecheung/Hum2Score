"""Detached, interactive notation preview windows."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
)

from .models import NoteEvent
from .widgets import NumberedNotationWidget, StaffWidget


class NotationViewer(QDialog):
    def __init__(
        self,
        kind: str,
        events: list[NoteEvent],
        play_callback: Callable[[], None],
        icon: QIcon,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.kind = kind
        self.play_callback = play_callback
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowIcon(icon)
        is_numbered = kind == "numbered"
        self.setWindowTitle("简谱查看器" if is_numbered else "五线谱查看器")
        self.resize(980, 610)
        self.setMinimumSize(720, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)
        heading = QHBoxLayout()
        title = QLabel("简谱" if is_numbered else "五线谱")
        title.setObjectName("viewerTitle")
        subtitle = QLabel(
            "数字唱名与估算时值" if is_numbered else "高音谱号 · 单声部主旋律"
        )
        subtitle.setObjectName("muted")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        heading.addStretch()
        layout.addLayout(heading)

        self.preview = NumberedNotationWidget() if is_numbered else StaffWidget()
        self.preview.set_events(events)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.preview)
        layout.addWidget(scroll, 1)

        actions = QHBoxLayout()
        actions.addStretch()
        play = QPushButton("▶  MIDI 预览")
        play.setObjectName("primaryExport")
        export = QPushButton("导出当前视图…")
        close = QPushButton("关闭")
        play.clicked.connect(self.play_callback)
        export.clicked.connect(self.export_image)
        close.clicked.connect(self.close)
        actions.addWidget(play)
        actions.addWidget(export)
        actions.addWidget(close)
        layout.addLayout(actions)

    def set_events(self, events: list[NoteEvent]) -> None:
        self.preview.set_events(events)

    def set_highlight(self, index: int | None) -> None:
        self.preview.set_highlight(index)

    def export_image(self) -> None:
        default = "hum2score-numbered.png" if self.kind == "numbered" else "hum2score-staff.png"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出乐谱图片", str(Path.home() / default), "PNG 图片 (*.png)"
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        if not self.preview.grab().save(path, "PNG"):
            QMessageBox.critical(self, "导出失败", "无法写入图片文件。")
