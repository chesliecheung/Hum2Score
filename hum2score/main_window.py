"""Main PyQt6 window and user interaction."""

from __future__ import annotations

import traceback
import sys
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QSystemTrayIcon,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .audio import AudioRecorder
from .models import NoteEvent
from .notation import (
    PITCH_CLASSES,
    duration_name,
    export_midi,
    export_numbered_text,
    numbered_name,
    octave_for_midi,
    pitch_name,
    solfege_name,
)
from .note_editor import NoteEditorDialog
from .pdf_export import export_score_pdf
from .pitch import CrepePitchDetector, PitchTrack
from .playback import MelodyPlayer, Metronome
from .project import load_project, save_project
from .quantizer import MelodyQuantizer, QuantizerConfig
from .notation_viewer import NotationViewer
from .widgets import NumberedNotationWidget, PitchPlot, StaffWidget


class AnalysisThread(QThread):
    completed = pyqtSignal(object, object, object)
    failed = pyqtSignal(str)

    def __init__(self, audio, sample_rate: int, confidence: float, config: QuantizerConfig):
        super().__init__()
        self.audio = audio
        self.sample_rate = sample_rate
        self.confidence = confidence
        self.config = config

    def run(self) -> None:
        try:
            track = CrepePitchDetector().analyze(
                self.audio, self.sample_rate, self.confidence
            )
            smooth, events = MelodyQuantizer(self.config).quantize(track)
            self.completed.emit(track, smooth, events)
        except Exception as exc:  # Keep worker failures out of the Qt event loop.
            traceback.print_exc()
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Hum2Score — 哼唱转乐谱")
        self.resize(1280, 900)
        self.setMinimumSize(1060, 760)
        if sys.platform == "darwin":
            # A real unified toolbar places product controls in the native title
            # region beside the traffic lights without faking window buttons.
            self.setUnifiedTitleAndToolBarOnMac(True)
        icon_path = self._resource_path("assets/hum2score-icon.png")
        if icon_path.exists() and sys.platform != "darwin":
            self.setWindowIcon(QIcon(str(icon_path)))
        self.recorder = AudioRecorder(16000)
        self.recorder.level_changed.connect(self._set_level)
        self.recorder.error.connect(lambda message: self.status_label.setText(message))
        self.events: list[NoteEvent] = []
        self.track: PitchTrack | None = None
        self.smooth_midi = None
        self.worker: AnalysisThread | None = None
        self.player = MelodyPlayer()
        self.player.note_started.connect(self._playback_note_started)
        self.player.finished.connect(self._playback_finished)
        self.player.failed.connect(self._playback_failed)
        self.metronome = Metronome()
        self.audio_samples: np.ndarray | None = None
        self.audio_sample_rate = self.recorder.sample_rate
        self.project_path: Path | None = None
        self._close_when_finished = False
        self._quitting = False
        self._tray_notice_shown = False
        self._mac_titlebar_configured = False
        self._viewer_windows: list[NotationViewer] = []
        self.elapsed = 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._tick)
        self._build_ui()
        self._apply_style()
        self._setup_tray()

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        if (
            sys.platform == "darwin"
            and QApplication.platformName() == "cocoa"
            and not self._mac_titlebar_configured
        ):
            self._mac_titlebar_configured = self._configure_native_macos_titlebar()

    def _configure_native_macos_titlebar(self) -> bool:
        """Extend content under the real Cocoa traffic lights and hide the title."""
        try:
            import ctypes
            import ctypes.util

            library = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
            library.sel_registerName.restype = ctypes.c_void_p
            library.sel_registerName.argtypes = [ctypes.c_char_p]
            selector = library.sel_registerName
            send_id = ctypes.CFUNCTYPE(
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
            )(("objc_msgSend", library))
            send_ulong = ctypes.CFUNCTYPE(
                ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p
            )(("objc_msgSend", library))
            send_void_ulong = ctypes.CFUNCTYPE(
                None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong
            )(("objc_msgSend", library))
            send_void_bool = ctypes.CFUNCTYPE(
                None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool
            )(("objc_msgSend", library))

            view = ctypes.c_void_p(int(self.winId()))
            window = send_id(view, selector(b"window"))
            if not window:
                return False
            send_void_bool(window, selector(b"setTitlebarAppearsTransparent:"), True)
            # NSWindowTitleHidden = 1. The native traffic lights remain intact.
            send_void_ulong(window, selector(b"setTitleVisibility:"), 1)
            return True
        except Exception:
            return False

    @staticmethod
    def _resource_path(relative: str) -> Path:
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        return base / relative

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("appRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 10 if sys.platform == "darwin" else 20, 24, 22)
        layout.setSpacing(16)

        # Header: product identity and the four-step mental model.
        header = QFrame()
        header.setObjectName("header")
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(70 if sys.platform == "darwin" else 4, 7, 12, 9)
        icon_label = QLabel()
        icon_label.setFixedSize(44, 44)
        icon = QPixmap(str(self._resource_path("assets/hum2score-icon.png")))
        if not icon.isNull():
            icon_label.setPixmap(
                icon.scaled(
                    QSize(44, 44),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        brand = QVBoxLayout()
        brand.setSpacing(1)
        title = QLabel("Hum2Score")
        title.setObjectName("title")
        subtitle = QLabel("把脑海里的旋律，变成看得见的音符")
        subtitle.setObjectName("subtitle")
        brand.addWidget(title)
        brand.addWidget(subtitle)
        title_row.addWidget(icon_label)
        title_row.addSpacing(9)
        title_row.addLayout(brand)
        title_row.addStretch()
        self.open_project_button = QPushButton("打开工程…")
        self.open_project_button.setObjectName("titleButton")
        self.open_project_button.clicked.connect(self.open_project)
        self.save_project_button = QPushButton("保存工程…")
        self.save_project_button.setObjectName("titleButton")
        self.save_project_button.clicked.connect(self.save_project_file)
        self.save_project_button.setEnabled(False)
        title_row.addWidget(self.open_project_button)
        title_row.addWidget(self.save_project_button)
        for text in ("1  录制", "2  识别", "3  校对", "4  导出"):
            chip = QLabel(text)
            chip.setObjectName("stepChip")
            title_row.addWidget(chip)
        header.setLayout(title_row)
        if sys.platform == "darwin":
            self.title_toolbar = QToolBar("Hum2Score", self)
            self.title_toolbar.setObjectName("nativeTitleToolbar")
            self.title_toolbar.setMovable(False)
            self.title_toolbar.setFloatable(False)
            self.title_toolbar.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
            self.title_toolbar.setMinimumHeight(62)
            self.title_toolbar.addWidget(header)
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.title_toolbar)
        else:
            layout.addWidget(header)

        # Recorder card: keep the primary action unmistakable, settings secondary.
        controls = QFrame()
        controls.setObjectName("card")
        control_layout = QHBoxLayout(controls)
        control_layout.setContentsMargins(20, 17, 20, 17)
        control_layout.setSpacing(24)
        record_column = QVBoxLayout()
        record_column.setSpacing(8)
        record_eyebrow = QLabel("01  ·  捕捉旋律")
        record_eyebrow.setObjectName("eyebrow")
        record_title = QLabel("对着麦克风，自然地哼出来")
        record_title.setObjectName("sectionTitle")
        record_hint = QLabel("只需要单声部人声；保持每个音清晰、稳定即可。")
        record_hint.setObjectName("muted")
        record_column.addWidget(record_eyebrow)
        record_column.addWidget(record_title)
        record_column.addWidget(record_hint)
        record_actions = QHBoxLayout()
        record_actions.setSpacing(10)
        self.start_button = QPushButton("●   开始录音")
        self.start_button.setObjectName("recordButton")
        self.start_button.setMinimumHeight(44)
        self.stop_button = QPushButton("■   停止并识别")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.setMinimumHeight(44)
        self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_recording)
        self.stop_button.clicked.connect(self.stop_recording)
        self.import_button = QPushButton("导入 WAV…")
        self.import_button.setMinimumHeight(44)
        self.import_button.clicked.connect(self.import_wav)
        record_actions.addWidget(self.start_button)
        record_actions.addWidget(self.stop_button)
        record_actions.addWidget(self.import_button)
        record_column.addLayout(record_actions)
        control_layout.addLayout(record_column, 4)

        divider = QFrame()
        divider.setObjectName("vDivider")
        divider.setFrameShape(QFrame.Shape.VLine)
        control_layout.addWidget(divider)

        monitor = QVBoxLayout()
        monitor.setSpacing(8)
        status_caption = QLabel("当前状态")
        status_caption.setObjectName("miniLabel")
        self.status_label = QLabel("准备就绪")
        self.status_label.setObjectName("status")
        level_row = QHBoxLayout()
        level_text = QLabel("麦克风电平")
        level_text.setObjectName("miniLabel")
        self.level = QProgressBar()
        self.level.setRange(0, 100)
        self.level.setTextVisible(False)
        self.level.setFixedHeight(8)
        level_row.addWidget(level_text)
        level_row.addWidget(self.level, 1)
        monitor.addWidget(status_caption)
        monitor.addWidget(self.status_label)
        monitor.addLayout(level_row)
        control_layout.addLayout(monitor, 2)

        divider2 = QFrame()
        divider2.setObjectName("vDivider")
        divider2.setFrameShape(QFrame.Shape.VLine)
        control_layout.addWidget(divider2)

        settings = QGridLayout()
        settings.setHorizontalSpacing(10)
        settings.setVerticalSpacing(7)
        settings_title = QLabel("识别灵敏度")
        settings_title.setObjectName("miniLabel")
        settings.addWidget(settings_title, 0, 0, 1, 2)
        self.confidence = QDoubleSpinBox()
        self.confidence.setRange(0.1, 0.95)
        self.confidence.setSingleStep(0.05)
        self.confidence.setValue(0.55)
        self.change_threshold = QDoubleSpinBox()
        self.change_threshold.setRange(0.3, 3.0)
        self.change_threshold.setSingleStep(0.1)
        self.change_threshold.setValue(0.7)
        self.change_threshold.setSuffix(" 半音")
        self.min_duration = QDoubleSpinBox()
        self.min_duration.setRange(0.05, 0.8)
        self.min_duration.setSingleStep(0.02)
        self.min_duration.setValue(0.12)
        self.min_duration.setSuffix(" 秒")
        for row, (label_text, control) in enumerate(
            (("置信度", self.confidence), ("换音阈值", self.change_threshold), ("最短音符", self.min_duration)),
            1,
        ):
            label = QLabel(label_text)
            label.setObjectName("miniLabel")
            settings.addWidget(label, row, 0)
            settings.addWidget(control, row, 1)
        self.metronome_checkbox = QCheckBox("录音时开启节拍器")
        self.metronome_checkbox.setToolTip("建议佩戴耳机，避免节拍声被麦克风录入")
        self.bpm_spin = QSpinBox()
        self.bpm_spin.setRange(40, 220)
        self.bpm_spin.setValue(90)
        self.bpm_spin.setSuffix(" BPM")
        settings.addWidget(self.metronome_checkbox, 4, 0)
        settings.addWidget(self.bpm_spin, 4, 1)
        control_layout.addLayout(settings, 2)
        layout.addWidget(controls)

        pitch_card = QFrame()
        pitch_card.setObjectName("card")
        pitch_layout = QVBoxLayout(pitch_card)
        pitch_layout.setContentsMargins(14, 12, 14, 10)
        pitch_layout.setSpacing(8)
        pitch_header = QHBoxLayout()
        pitch_title = QLabel("02  ·  音高轨迹")
        pitch_title.setObjectName("cardTitle")
        pitch_helper = QLabel("灰色为原始检测 · 紫色为抗抖动后的主旋律")
        pitch_helper.setObjectName("muted")
        pitch_header.addWidget(pitch_title)
        pitch_header.addStretch()
        pitch_header.addWidget(pitch_helper)
        pitch_layout.addLayout(pitch_header)
        self.pitch_plot = PitchPlot()
        pitch_layout.addWidget(self.pitch_plot)
        layout.addWidget(pitch_card)

        splitter = QSplitter()
        splitter.setObjectName("workspaceSplitter")
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 6, 0)
        left_card = QFrame()
        left_card.setObjectName("card")
        left_card_layout = QVBoxLayout(left_card)
        left_card_layout.setContentsMargins(14, 12, 14, 14)
        left_card_layout.setSpacing(9)
        table_title = QHBoxLayout()
        table_heading = QLabel("03  ·  音符校对")
        table_heading.setObjectName("cardTitle")
        table_title.addWidget(table_heading)
        table_title.addStretch()
        edit_hint = QLabel("点击 ▶ 试听 · 双击修改")
        edit_hint.setObjectName("muted")
        table_title.addWidget(edit_hint)
        self.add_note_button = QPushButton("＋ 新增")
        self.add_note_button.setObjectName("compactButton")
        self.add_note_button.clicked.connect(self.add_note)
        table_title.addWidget(self.add_note_button)
        self.modify_button = QPushButton("修改…")
        self.modify_button.setObjectName("compactButton")
        self.modify_button.clicked.connect(self.modify_selected_note)
        self.modify_button.setEnabled(False)
        table_title.addWidget(self.modify_button)
        playback_row = QHBoxLayout()
        playback_label = QLabel("播放校验")
        playback_label.setObjectName("miniLabel")
        playback_row.addWidget(playback_label)
        playback_row.addStretch()
        self.play_selected_button = QPushButton("▶  选中")
        self.play_selected_button.setObjectName("compactButton")
        self.play_selected_button.clicked.connect(self.play_selected_note)
        self.play_selected_button.setEnabled(False)
        playback_row.addWidget(self.play_selected_button)
        self.play_audio_button = QPushButton("▶  原始音频")
        self.play_audio_button.setObjectName("compactButton")
        self.play_audio_button.clicked.connect(self.play_original_audio)
        self.play_audio_button.setEnabled(False)
        playback_row.addWidget(self.play_audio_button)
        self.play_all_button = QPushButton("▶  MIDI 预览")
        self.play_all_button.setObjectName("compactButton")
        self.play_all_button.clicked.connect(self.play_all_notes)
        self.play_all_button.setEnabled(False)
        playback_row.addWidget(self.play_all_button)
        self.stop_playback_button = QPushButton("■")
        self.stop_playback_button.setObjectName("compactButton")
        self.stop_playback_button.setToolTip("停止播放")
        self.stop_playback_button.clicked.connect(self.stop_playback)
        self.stop_playback_button.setEnabled(False)
        playback_row.addWidget(self.stop_playback_button)
        self.delete_button = QPushButton("删除")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.clicked.connect(self.delete_selected)
        self.delete_button.setEnabled(False)
        table_title.addWidget(self.delete_button)
        left_card_layout.addLayout(table_title)
        left_card_layout.addLayout(playback_row)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["试听", "#", "简谱", "唱名", "音名", "八度", "时长", "估算时值"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellClicked.connect(self._table_cell_clicked)
        self.table.cellDoubleClicked.connect(self.edit_note)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        left_card_layout.addWidget(self.table)
        left_layout.addWidget(left_card)

        previews = QWidget()
        previews_layout = QVBoxLayout(previews)
        previews_layout.setContentsMargins(6, 0, 0, 0)
        preview_card = QFrame()
        preview_card.setObjectName("card")
        preview_card_layout = QVBoxLayout(preview_card)
        preview_card_layout.setContentsMargins(14, 12, 14, 14)
        preview_heading = QLabel("乐谱预览 · 点击放大查看")
        preview_heading.setObjectName("cardTitle")
        preview_card_layout.addWidget(preview_heading)
        self.numbered_widget = NumberedNotationWidget()
        self.staff_widget = StaffWidget()
        self.numbered_widget.activated.connect(lambda: self.open_notation("numbered"))
        self.staff_widget.activated.connect(lambda: self.open_notation("staff"))
        numbered_header = QHBoxLayout()
        numbered_label = QLabel("简谱")
        numbered_label.setObjectName("miniLabel")
        self.open_numbered_button = QPushButton("放大查看 ↗")
        self.open_numbered_button.setObjectName("linkButton")
        self.open_numbered_button.clicked.connect(lambda: self.open_notation("numbered"))
        numbered_header.addWidget(numbered_label)
        numbered_header.addStretch()
        numbered_header.addWidget(self.open_numbered_button)
        numbered_scroll = QScrollArea()
        numbered_scroll.setWidgetResizable(True)
        numbered_scroll.setWidget(self.numbered_widget)
        staff_header = QHBoxLayout()
        staff_label = QLabel("五线谱")
        staff_label.setObjectName("miniLabel")
        self.open_staff_button = QPushButton("放大查看 ↗")
        self.open_staff_button.setObjectName("linkButton")
        self.open_staff_button.clicked.connect(lambda: self.open_notation("staff"))
        staff_header.addWidget(staff_label)
        staff_header.addStretch()
        staff_header.addWidget(self.open_staff_button)
        staff_scroll = QScrollArea()
        staff_scroll.setWidgetResizable(True)
        staff_scroll.setWidget(self.staff_widget)
        preview_card_layout.addLayout(numbered_header)
        preview_card_layout.addWidget(numbered_scroll)
        preview_card_layout.addLayout(staff_header)
        preview_card_layout.addWidget(staff_scroll)
        previews_layout.addWidget(preview_card)
        splitter.addWidget(left)
        splitter.addWidget(previews)
        splitter.setSizes([540, 660])
        layout.addWidget(splitter, 1)

        export_card = QFrame()
        export_card.setObjectName("exportBar")
        export_row = QHBoxLayout()
        export_row.setContentsMargins(16, 10, 12, 10)
        export_title = QLabel("04  ·  导出作品")
        export_title.setObjectName("cardTitle")
        export_row.addWidget(export_title)
        export_row.addStretch()
        self.export_text_button = QPushButton("导出简谱文本…")
        self.export_midi_button = QPushButton("导出 MIDI…")
        self.export_midi_button.setObjectName("primaryExport")
        self.export_numbered_image_button = QPushButton("简谱图片…")
        self.export_staff_image_button = QPushButton("五线谱图片…")
        self.export_pdf_button = QPushButton("PDF 乐谱…")
        for button in (
            self.export_text_button,
            self.export_midi_button,
            self.export_numbered_image_button,
            self.export_staff_image_button,
            self.export_pdf_button,
        ):
            button.setEnabled(False)
            export_row.addWidget(button)
        export_row.addStretch()
        self.export_text_button.clicked.connect(self.export_text)
        self.export_midi_button.clicked.connect(self.export_midi_file)
        self.export_numbered_image_button.clicked.connect(
            lambda: self.export_image(self.numbered_widget, "hum2score-numbered.png")
        )
        self.export_staff_image_button.clicked.connect(
            lambda: self.export_image(self.staff_widget, "hum2score-staff.png")
        )
        self.export_pdf_button.clicked.connect(self.export_pdf_file)
        export_card.setLayout(export_row)
        layout.addWidget(export_card)
        self.setCentralWidget(root)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget#appRoot { background: #F3F5FA; color: #182033; }
            QWidget { color: #20283A; font-size: 13px; }
            QLabel { color: #20283A; background: transparent; }
            QDialog, QMessageBox { background: #F3F5FA; color: #20283A; }
            QFrame#header { background: transparent; border: none; }
            QToolBar#nativeTitleToolbar { background: transparent; border: none; spacing: 0px; padding: 0px; }
            QFrame#card, QFrame#exportBar { background: #FFFFFF; border: 1px solid #E1E5EE; border-radius: 12px; }
            QFrame#vDivider { color: #E7EAF1; }
            QLabel#title { font-size: 24px; font-weight: 750; color: #201A55; }
            QLabel#subtitle, QLabel#muted { color: #7B8498; font-size: 12px; }
            QLabel#stepChip { background: #F2F0FF; color: #5B4AD8; border-radius: 12px; padding: 5px 10px; font-size: 11px; font-weight: 650; }
            QLabel#eyebrow { color: #6B5CE7; font-size: 11px; font-weight: 700; }
            QLabel#sectionTitle { color: #171D2C; font-size: 17px; font-weight: 700; }
            QLabel#cardTitle { color: #20283A; font-size: 13px; font-weight: 700; }
            QLabel#miniLabel { color: #7A8497; font-size: 11px; }
            QLabel#status { color: #4F3FD1; background: #F0EEFF; border-radius: 8px; padding: 7px 10px; font-weight: 700; }
            QPushButton { background: #FFFFFF; color: #364054; border: 1px solid #D7DCE7; border-radius: 8px; padding: 7px 13px; font-weight: 600; }
            QPushButton:hover { background: #F7F6FF; border-color: #7668EB; color: #5141D4; }
            QPushButton:pressed { background: #ECE9FF; }
            QPushButton:disabled { color: #AEB5C2; background: #F4F5F8; border-color: #E5E8EE; }
            QPushButton#recordButton, QPushButton#primaryExport { color: white; background: #635BEB; border-color: #635BEB; font-weight: 700; }
            QPushButton#recordButton:hover, QPushButton#primaryExport:hover { background: #554CD7; border-color: #554CD7; }
            QPushButton#stopButton { background: #252A3A; color: white; border-color: #252A3A; }
            QPushButton#dangerButton { color: #C63D51; }
            QPushButton#titleButton { color: #485166; background: rgba(255,255,255,0.74); padding: 6px 10px; }
            QPushButton#compactButton { padding: 5px 9px; min-width: 28px; }
            QPushButton#linkButton { color: #5B4AD8; background: transparent; border: none; padding: 2px 5px; font-size: 11px; }
            QPushButton#linkButton:hover { color: #4032B5; background: #F2F0FF; }
            QLabel#viewerTitle { font-size: 24px; font-weight: 750; color: #201A55; }
            QDoubleSpinBox, QSpinBox, QComboBox { background: #F8F9FC; border: 1px solid #DDE1EA; border-radius: 7px; padding: 5px 8px; min-width: 88px; }
            QDoubleSpinBox, QSpinBox, QComboBox, QLineEdit { color: #182033; selection-background-color: #DCD7FF; selection-color: #182033; }
            QComboBox::drop-down { border: none; width: 26px; background: #EEF0F6; border-top-right-radius: 7px; border-bottom-right-radius: 7px; }
            QComboBox QAbstractItemView { background: #FFFFFF; color: #182033; border: 1px solid #C9CFDB; outline: none; padding: 5px; selection-background-color: #E6E2FF; selection-color: #241A68; }
            QComboBox QAbstractItemView::item { color: #182033; background: #FFFFFF; min-height: 30px; padding: 4px 9px; }
            QComboBox QAbstractItemView::item:selected { color: #241A68; background: #E6E2FF; }
            QCheckBox { color: #394359; spacing: 7px; }
            QTableWidget { background: white; alternate-background-color: #F8F9FC; border: 1px solid #EAECF2; border-radius: 8px; selection-background-color: #EAE7FF; selection-color: #27203D; }
            QHeaderView::section { background: #F5F6FA; color: #667085; padding: 8px; border: none; border-bottom: 1px solid #E5E8EF; font-size: 11px; font-weight: 650; }
            QScrollArea { background: white; border: 1px solid #EAECF2; border-radius: 8px; }
            QScrollArea > QWidget > QWidget { background: #FFFFFF; }
            QMenu { background: #FFFFFF; color: #20283A; border: 1px solid #D9DEE8; padding: 6px; }
            QMenu::item { padding: 6px 24px 6px 12px; border-radius: 5px; }
            QMenu::item:selected { background: #ECE9FF; color: #33279D; }
            QProgressBar { border: none; background: #ECEEF4; border-radius: 4px; }
            QProgressBar::chunk { background: #31C994; border-radius: 4px; }
            QSplitter::handle { background: transparent; width: 8px; }
            """
        )
        # Apply globally as macOS renders combo-box popup views and tray menus
        # in separate native windows that do not reliably inherit window QSS.
        QApplication.instance().setStyleSheet(self.styleSheet())

    def _setup_tray(self) -> None:
        """Install a persistent macOS menu-bar controller."""
        tray_icon_path = self._resource_path("assets/Hum2ScoreTemplate.png")
        tray_icon = QIcon(str(tray_icon_path))
        if tray_icon.isNull():
            tray_icon = self.windowIcon()
        tray_icon.setIsMask(True)
        self.tray = QSystemTrayIcon(tray_icon, self)
        self.tray.setToolTip("Hum2Score · 准备就绪")
        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        self.tray_status_action = QAction("●  准备就绪", menu)
        self.tray_status_action.setEnabled(False)
        self.tray_record_action = QAction("开始录音", menu)
        self.tray_stop_action = QAction("停止并解析", menu)
        self.tray_import_action = QAction("导入 WAV…", menu)
        self.tray_open_action = QAction("打开工程…", menu)
        self.tray_save_action = QAction("保存工程…", menu)
        self.tray_play_action = QAction("播放 MIDI 预览", menu)
        self.tray_audio_action = QAction("播放原始音频", menu)
        self.tray_stop_playback_action = QAction("停止播放", menu)
        self.tray_show_action = QAction("显示 Hum2Score", menu)
        self.tray_quit_action = QAction("退出 Hum2Score", menu)
        self.tray_record_action.triggered.connect(self.start_recording)
        self.tray_stop_action.triggered.connect(self.stop_recording)
        self.tray_import_action.triggered.connect(self._tray_import_wav)
        self.tray_open_action.triggered.connect(self._tray_open_project)
        self.tray_save_action.triggered.connect(self._tray_save_project)
        self.tray_play_action.triggered.connect(self.play_all_notes)
        self.tray_audio_action.triggered.connect(self.play_original_audio)
        self.tray_stop_playback_action.triggered.connect(self.stop_playback)
        self.tray_show_action.triggered.connect(self.show_window)
        self.tray_quit_action.triggered.connect(self.quit_application)
        menu.addAction(self.tray_status_action)
        menu.addSeparator()
        menu.addAction(self.tray_record_action)
        menu.addAction(self.tray_stop_action)
        menu.addAction(self.tray_import_action)
        menu.addSeparator()
        menu.addAction(self.tray_open_action)
        menu.addAction(self.tray_save_action)
        playback_menu = menu.addMenu("播放与校验")
        playback_menu.addAction(self.tray_play_action)
        playback_menu.addAction(self.tray_audio_action)
        playback_menu.addSeparator()
        playback_menu.addAction(self.tray_stop_playback_action)
        menu.addSeparator()
        menu.addAction(self.tray_show_action)
        menu.addAction(self.tray_quit_action)
        self.tray.setContextMenu(menu)
        # On macOS, clicking a status item with a context menu already opens
        # that menu. Handling Trigger as well can race with Cocoa activation
        # and unexpectedly change/close the front window.
        if sys.platform != "darwin":
            self.tray.activated.connect(self._tray_activated)
        self.tray.show()
        self._sync_tray_actions("准备就绪")

    def _sync_tray_actions(self, status: str | None = None) -> None:
        if not hasattr(self, "tray_record_action"):
            return
        recording = self.recorder.is_recording
        analyzing = bool(self.worker and self.worker.isRunning())
        self.tray_record_action.setEnabled(not recording and not analyzing)
        self.tray_stop_action.setEnabled(recording)
        self.tray_import_action.setEnabled(not recording and not analyzing)
        self.tray_open_action.setEnabled(not recording and not analyzing)
        self.tray_save_action.setEnabled(
            not recording and not analyzing and (bool(self.events) or self.audio_samples is not None)
        )
        self.tray_play_action.setEnabled(bool(self.events) and not recording)
        self.tray_audio_action.setEnabled(self.audio_samples is not None and not recording)
        self.tray_stop_playback_action.setEnabled(self.player.is_playing)
        if status is not None:
            self.tray_status_action.setText(f"●  {status}")
            self.tray.setToolTip(f"Hum2Score · {status}")

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_window()

    def _tray_import_wav(self) -> None:
        self.show_window()
        QTimer.singleShot(0, self.import_wav)

    def _tray_open_project(self) -> None:
        self.show_window()
        QTimer.singleShot(0, self.open_project)

    def _tray_save_project(self) -> None:
        self.show_window()
        QTimer.singleShot(0, self.save_project_file)

    def show_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def quit_application(self) -> None:
        self._quitting = True
        self.player.stop(emit_finished=False)
        if self.recorder.is_recording:
            self.recorder.stop()
        if self.worker and self.worker.isRunning():
            self._close_when_finished = True
            self.status_label.setText("正在安全结束分析…")
            self.hide()
            return
        self.tray.hide()
        QApplication.instance().quit()

    def _selection_changed(self) -> None:
        selected = bool(self.table.selectionModel().selectedRows())
        self.delete_button.setEnabled(selected)
        self.modify_button.setEnabled(selected)
        self.play_selected_button.setEnabled(selected and bool(self.events))

    def _table_cell_clicked(self, row: int, column: int) -> None:
        if column == 0:
            self.play_note(row)

    def play_selected_note(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if rows:
            self.play_note(rows[0].row())

    def play_note(self, row: int) -> None:
        if self.recorder.is_recording or not (0 <= row < len(self.events)):
            return
        if not self.player.play([self.events[row]], [row]):
            return
        self.stop_playback_button.setEnabled(True)
        self.status_label.setText(f"正在试听：{pitch_name(self.events[row].midi)}")
        self._sync_tray_actions("正在试听")

    def play_all_notes(self) -> None:
        if self.recorder.is_recording or not self.events:
            return
        if not self.player.play(
            self.events, list(range(len(self.events))), respect_timeline=True
        ):
            return
        self.stop_playback_button.setEnabled(True)
        self.status_label.setText(f"正在播放全部 {len(self.events)} 个音符")
        self._sync_tray_actions("正在播放 MIDI 预览")

    def play_original_audio(self) -> None:
        if self.recorder.is_recording or self.audio_samples is None:
            return
        if not self.player.play_audio(
            self.audio_samples, self.audio_sample_rate, self.events
        ):
            return
        self.stop_playback_button.setEnabled(True)
        self.status_label.setText("正在播放原始音频 · 乐谱与曲线同步跟随")
        self._sync_tray_actions("正在播放原始音频")

    def stop_playback(self) -> None:
        self.player.stop()

    def _playback_note_started(self, row: int) -> None:
        if 0 <= row < self.table.rowCount():
            self.table.selectRow(row)
            self.table.scrollToItem(self.table.item(row, 0))
            self.numbered_widget.set_highlight(row)
            self.staff_widget.set_highlight(row)
            self.pitch_plot.set_playback_index(row, self.events)
            for viewer in list(self._viewer_windows):
                viewer.set_highlight(row)

    def _playback_finished(self) -> None:
        self.stop_playback_button.setEnabled(False)
        self._clear_playback_highlight()
        self.status_label.setText(
            f"准备就绪 · 当前 {len(self.events)} 个音符" if self.events else "准备就绪"
        )
        self._sync_tray_actions()

    def _clear_playback_highlight(self) -> None:
        self.numbered_widget.set_highlight(None)
        self.staff_widget.set_highlight(None)
        self.pitch_plot.set_playback_index(None, self.events)
        for viewer in list(self._viewer_windows):
            viewer.set_highlight(None)

    def _playback_failed(self, message: str) -> None:
        self.stop_playback_button.setEnabled(False)
        self._clear_playback_highlight()
        self.status_label.setText("播放失败")
        self._sync_tray_actions("播放失败")
        QMessageBox.critical(self, "无法播放", f"无法打开音频输出：\n{message}")

    def open_notation(self, kind: str) -> None:
        if not self.events:
            QMessageBox.information(self, "暂无乐谱", "请先录制并解析一段旋律。")
            return
        viewer = NotationViewer(kind, self.events, self.play_all_notes, self.windowIcon(), self)
        self._viewer_windows.append(viewer)
        viewer.destroyed.connect(lambda _=None, v=viewer: self._remove_viewer(v))
        viewer.show()
        viewer.raise_()

    def _remove_viewer(self, viewer: NotationViewer) -> None:
        if viewer in self._viewer_windows:
            self._viewer_windows.remove(viewer)

    def _set_level(self, level: float) -> None:
        self.level.setValue(round(level * 100))

    def _tick(self) -> None:
        self.elapsed += 0.1
        self.status_label.setText(f"正在录音  {self.elapsed:.1f} 秒")
        if round(self.elapsed * 10) % 5 == 0:
            self._sync_tray_actions(f"正在录音 {self.elapsed:.1f} 秒")

    def start_recording(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        self.player.stop(emit_finished=False)
        self._clear_playback_highlight()
        self.stop_playback_button.setEnabled(False)
        try:
            self.recorder.start()
        except Exception as exc:
            QMessageBox.critical(self, "无法录音", f"无法打开麦克风：\n{exc}")
            return
        self.elapsed = 0.0
        self.timer.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("正在录音…请开始哼唱")
        self.play_all_button.setEnabled(False)
        self.play_selected_button.setEnabled(False)
        self.play_audio_button.setEnabled(False)
        self.import_button.setEnabled(False)
        if self.metronome_checkbox.isChecked():
            self.metronome.start(self.bpm_spin.value())
        self._sync_tray_actions("正在录音")

    def stop_recording(self) -> None:
        self.timer.stop()
        self.metronome.stop()
        audio = self.recorder.stop()
        self.stop_button.setEnabled(False)
        self.level.setValue(0)
        if audio.size == 0:
            self.start_button.setEnabled(True)
            self.import_button.setEnabled(True)
            self._sync_tray_actions("准备就绪")
            QMessageBox.warning(self, "没有录音", "未收到音频，请检查麦克风。")
            return
        self.audio_samples = audio
        self.audio_sample_rate = self.recorder.sample_rate
        self._analyze_audio(audio, self.recorder.sample_rate, "麦克风录音")

    def _analyze_audio(self, audio: np.ndarray, sample_rate: int, source: str) -> None:
        self.player.stop(emit_finished=False)
        self._clear_playback_highlight()
        # A new source starts a new unsaved project. Clear the prior melody so
        # an analysis failure can never pair new audio with stale old notes.
        self.events = []
        self.track = None
        self.smooth_midi = None
        self.project_path = None
        self.pitch_plot.clear()
        self.refresh_results()
        self.status_label.setText(f"CREPE 正在解析{source}…")
        self.start_button.setEnabled(False)
        self.import_button.setEnabled(False)
        config = QuantizerConfig(
            change_threshold=self.change_threshold.value(),
            min_note_duration=self.min_duration.value(),
        )
        self.worker = AnalysisThread(
            audio, sample_rate, self.confidence.value(), config
        )
        self.worker.completed.connect(self.analysis_completed)
        self.worker.failed.connect(self.analysis_failed)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()
        self._sync_tray_actions("正在解析")

    def import_wav(self) -> None:
        if self.recorder.is_recording or (self.worker and self.worker.isRunning()):
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "导入 WAV 音频", str(Path.home()), "WAV 音频 (*.wav *.wave)"
        )
        if not path:
            return
        try:
            from scipy.io import wavfile

            sample_rate, audio = wavfile.read(path)
            audio = np.asarray(audio)
            if np.issubdtype(audio.dtype, np.integer):
                info = np.iinfo(audio.dtype)
                scale = max(abs(info.min), abs(info.max))
                audio = audio.astype(np.float32) / scale
            else:
                audio = audio.astype(np.float32)
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            audio = np.nan_to_num(audio)
            if audio.size == 0:
                raise ValueError("WAV 文件中没有音频数据。")
        except Exception as exc:
            QMessageBox.critical(self, "无法导入", f"读取 WAV 文件失败：\n{exc}")
            return
        self.audio_samples = audio
        self.audio_sample_rate = int(sample_rate)
        self.project_path = None
        self._analyze_audio(audio, int(sample_rate), f" {Path(path).name}")

    def _worker_finished(self) -> None:
        self.worker = None
        self._sync_tray_actions()
        if self._quitting:
            self.tray.hide()
            QTimer.singleShot(0, QApplication.instance().quit)

    def analysis_completed(self, track: PitchTrack, smooth, events: list[NoteEvent]) -> None:
        self.track, self.smooth_midi, self.events = track, smooth, list(events)
        self.start_button.setEnabled(True)
        self.import_button.setEnabled(True)
        self.play_audio_button.setEnabled(self.audio_samples is not None)
        if not self.events:
            self.status_label.setText("未识别到稳定音符")
            QMessageBox.information(
                self,
                "没有识别结果",
                "没有找到足够稳定的音符。请靠近麦克风、延长每个音，或降低置信度。",
            )
        else:
            self.status_label.setText(f"解析完成：识别到 {len(self.events)} 个音符")
            self.tray.showMessage(
                "Hum2Score 解析完成",
                f"识别到 {len(self.events)} 个音符，点击菜单栏图标查看。",
                QSystemTrayIcon.MessageIcon.Information,
                3500,
            )
        self.pitch_plot.set_track(track.times, track.midi, smooth)
        self.refresh_results()
        self._sync_tray_actions(f"已识别 {len(self.events)} 个音符")

    def analysis_failed(self, message: str) -> None:
        self.start_button.setEnabled(True)
        self.import_button.setEnabled(True)
        self.play_audio_button.setEnabled(self.audio_samples is not None)
        self.status_label.setText("解析失败")
        self._sync_tray_actions("解析失败")
        QMessageBox.critical(self, "解析失败", message)

    def refresh_results(self) -> None:
        self.table.setRowCount(len(self.events))
        for row, event in enumerate(self.events):
            values = (
                "▶",
                str(row + 1),
                numbered_name(event.midi),
                solfege_name(event.midi),
                pitch_name(event.midi),
                str(octave_for_midi(event.midi)),
                f"{event.duration:.2f} 秒",
                duration_name(event.quarter_length),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setToolTip("点击试听这个音符")
                if event.confidence < 0.65:
                    item.setBackground(QColor("#fff4d6"))
                    item.setToolTip(f"识别置信度较低：{event.confidence:.0%}")
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        self.numbered_widget.set_events(self.events)
        self.staff_widget.set_events(self.events)
        for viewer in list(self._viewer_windows):
            viewer.set_events(self.events)
        enabled = bool(self.events)
        for button in (
            self.export_text_button,
            self.export_midi_button,
            self.export_numbered_image_button,
            self.export_staff_image_button,
            self.export_pdf_button,
        ):
            button.setEnabled(enabled)
        self.play_all_button.setEnabled(enabled and not self.recorder.is_recording)
        self.play_audio_button.setEnabled(
            self.audio_samples is not None and not self.recorder.is_recording
        )
        self.save_project_button.setEnabled(enabled or self.audio_samples is not None)
        self.open_numbered_button.setEnabled(enabled)
        self.open_staff_button.setEnabled(enabled)
        self._sync_tray_actions()

    def edit_note(self, row: int, column: int) -> None:
        if column == 0 or not (0 <= row < len(self.events)):
            return
        self._edit_row(row)

    def modify_selected_note(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if rows:
            self._edit_row(rows[0].row())

    def _edit_row(self, row: int) -> None:
        if not (0 <= row < len(self.events)):
            return
        self.player.stop(emit_finished=False)
        self._playback_finished()
        dialog = NoteEditorDialog(self.events[row], "修改音符", self)
        dialog.setWindowIcon(self.windowIcon())
        if dialog.exec():
            updated = dialog.note_event()
            self.events[row] = updated
            self.events.sort(key=lambda item: item.start)
            self.refresh_results()
            updated_row = next(
                index for index, item in enumerate(self.events) if item is updated
            )
            self.table.selectRow(updated_row)
            self.status_label.setText("音符已修改，播放与乐谱已同步更新")

    def add_note(self) -> None:
        self.player.stop(emit_finished=False)
        self._playback_finished()
        if self.events:
            previous = self.events[-1]
            seed = NoteEvent(previous.midi, previous.end, previous.duration, 1.0, previous.quarter_length)
        else:
            seed = NoteEvent(60, 0.0, 0.5, 1.0, 1.0)
        dialog = NoteEditorDialog(seed, "新增音符", self)
        dialog.setWindowIcon(self.windowIcon())
        if dialog.exec():
            created = dialog.note_event()
            self.events.append(created)
            self.events.sort(key=lambda item: item.start)
            self.refresh_results()
            created_row = next(
                index for index, item in enumerate(self.events) if item is created
            )
            self.table.selectRow(created_row)
            self.status_label.setText("已新增音符")

    def delete_selected(self) -> None:
        self.player.stop(emit_finished=False)
        self._playback_finished()
        rows = sorted(
            {index.row() for index in self.table.selectionModel().selectedRows()}, reverse=True
        )
        for row in rows:
            del self.events[row]
        self.refresh_results()
        self.status_label.setText(f"已编辑：当前 {len(self.events)} 个音符")

    def _save_path(self, caption: str, default: str, file_filter: str) -> str:
        path, _ = QFileDialog.getSaveFileName(self, caption, str(Path.home() / default), file_filter)
        return path

    def save_project_file(self) -> None:
        if not self.events and self.audio_samples is None:
            return
        default = self.project_path.name if self.project_path else "untitled.hum2score"
        path = self._save_path(
            "保存 Hum2Score 工程", default, "Hum2Score 工程 (*.hum2score)"
        )
        if not path:
            return
        if not path.lower().endswith(".hum2score"):
            path += ".hum2score"
        try:
            save_project(
                path,
                self.events,
                self.audio_samples,
                self.audio_sample_rate,
                self.track,
                self.smooth_midi,
            )
            self.project_path = Path(path)
            self.status_label.setText(f"工程已保存：{self.project_path.name}")
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", str(exc))

    def open_project(self) -> None:
        if self.recorder.is_recording or (self.worker and self.worker.isRunning()):
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "打开 Hum2Score 工程", str(Path.home()), "Hum2Score 工程 (*.hum2score)"
        )
        if not path:
            return
        try:
            events, audio, rate, track, smooth = load_project(path)
        except Exception as exc:
            QMessageBox.critical(self, "打开失败", str(exc))
            return
        self.player.stop(emit_finished=False)
        self._clear_playback_highlight()
        self.events = events
        self.audio_samples = audio
        self.audio_sample_rate = rate
        self.track, self.smooth_midi = track, smooth
        self.project_path = Path(path)
        if track is not None and smooth is not None:
            self.pitch_plot.set_track(track.times, track.midi, smooth)
        else:
            self.pitch_plot.clear()
        self.refresh_results()
        self.status_label.setText(f"工程已打开：{self.project_path.name}")

    def export_text(self) -> None:
        path = self._save_path("导出简谱文本", "hum2score.txt", "文本文件 (*.txt)")
        if path:
            export_numbered_text(self.events, path)
            self.status_label.setText(f"已导出：{Path(path).name}")

    def export_midi_file(self) -> None:
        path = self._save_path("导出 MIDI", "hum2score.mid", "MIDI 文件 (*.mid *.midi)")
        if path:
            try:
                export_midi(self.events, path)
                self.status_label.setText(f"已导出：{Path(path).name}")
            except Exception as exc:
                QMessageBox.critical(self, "导出失败", str(exc))

    def export_pdf_file(self) -> None:
        path = self._save_path("导出 PDF 乐谱", "hum2score-score.pdf", "PDF 文件 (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            export_score_pdf(self.events, path)
            self.status_label.setText(f"已导出：{Path(path).name}")
        except Exception as exc:
            QMessageBox.critical(self, "PDF 导出失败", str(exc))

    def export_image(self, widget: QWidget, default: str) -> None:
        path = self._save_path("导出图片", default, "PNG 图片 (*.png)")
        if path:
            if not path.lower().endswith(".png"):
                path += ".png"
            ok = widget.grab().save(path, "PNG")
            if not ok:
                QMessageBox.critical(self, "导出失败", "无法写入图片文件。")
            else:
                self.status_label.setText(f"已导出：{Path(path).name}")

    def closeEvent(self, event) -> None:  # noqa: ANN001
        if self._quitting:
            event.accept()
            return
        self.hide()
        event.ignore()
        if not self._tray_notice_shown:
            self.tray.showMessage(
                "Hum2Score 仍在菜单栏运行",
                "窗口已隐藏；可从菜单栏直接录音、停止解析或退出。",
                QSystemTrayIcon.MessageIcon.Information,
                3500,
            )
            self._tray_notice_shown = True
