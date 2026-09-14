"""Self-contained PDF sheet export without requiring MuseScore."""

from __future__ import annotations

import math
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .models import NoteEvent
from .notation import NATURAL_PCS, duration_name, numbered_name, pitch_name


def _font() -> str:
    for path, name in (
        ("/System/Library/Fonts/STHeiti Medium.ttc", "Hum2ScoreCJK"),
        ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "Hum2ScoreCJK"),
        ("C:/Windows/Fonts/msyh.ttc", "Hum2ScoreCJK"),
    ):
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont(name, path, subfontIndex=0))
                return name
            except Exception:
                continue
    return "Helvetica"


def _music_symbol_font() -> str | None:
    """Use the native macOS symbol font for the treble-clef glyph when available."""
    path = Path("/System/Library/Fonts/Apple Symbols.ttf")
    if path.exists():
        try:
            pdfmetrics.registerFont(TTFont("Hum2ScoreSymbols", str(path)))
            return "Hum2ScoreSymbols"
        except Exception:
            pass
    return None


def _diatonic_index(midi: int) -> int:
    octave = midi // 12 - 1
    pc = midi % 12
    nearest = min(range(7), key=lambda index: abs(NATURAL_PCS[index] - pc))
    return octave * 7 + nearest


def export_score_pdf(events: list[NoteEvent], path: str | Path) -> None:
    if not events:
        raise ValueError("没有可导出的音符。")
    width, height = landscape(A4)
    output = canvas.Canvas(str(path), pagesize=(width, height))
    font = _font()
    margin = 52

    symbol_font = _music_symbol_font()
    right = width - margin
    page_size = 26
    page_count = math.ceil(len(events) / page_size)

    def draw_clef(staff_top: float) -> None:
        if symbol_font:
            output.setFont(symbol_font, 28)
            output.setFillColor(HexColor("#262635"))
            output.drawString(margin + 3, staff_top + 4, "𝄞")
        else:
            output.setStrokeColor(HexColor("#262635"))
            output.setLineWidth(1.7)
            output.bezier(
                margin + 24, staff_top + 43,
                margin + 2, staff_top + 30,
                margin + 10, staff_top + 5,
                margin + 28, staff_top + 16,
            )
            output.circle(margin + 20, staff_top + 15, 7, fill=0, stroke=1)
            output.line(margin + 20, staff_top + 48, margin + 20, staff_top - 5)

    def draw_staff(items: list[NoteEvent], staff_top: float) -> None:
        spacing = 11
        for line in range(5):
            y = staff_top + line * spacing
            output.setStrokeColor(HexColor("#5B6070"))
            output.setLineWidth(0.7)
            output.line(margin, y, right, y)
        draw_clef(staff_top)
        available = right - margin - 84
        step = min(49, available / max(1, len(items)))
        for index, event in enumerate(items):
            x = margin + 76 + index * step
            y = staff_top + 4 * spacing - (_diatonic_index(event.midi) - 30) * spacing / 2
            output.setFillColor(HexColor("#171723"))
            output.saveState()
            output.translate(x, y)
            output.rotate(-18)
            output.ellipse(-6, -4, 6, 4, fill=1, stroke=0)
            output.restoreState()
            if event.quarter_length < 4:
                output.setStrokeColor(HexColor("#171723"))
                output.setLineWidth(1.1)
                output.line(x + 5, y, x + 5, y + 29)
            output.setFont(font, 7)
            output.setFillColor(HexColor("#596174"))
            output.drawCentredString(
                x, staff_top - 17, pitch_name(event.midi).replace("♯", "#")
            )

    for page_index in range(page_count):
        start = page_index * page_size
        page_events = events[start : start + page_size]
        output.setFillColor(HexColor("#1E1A4D"))
        output.setFont(font, 24)
        output.drawString(margin, height - 54, "Hum2Score 乐谱")
        output.setFillColor(HexColor("#747E91"))
        output.setFont(font, 9)
        output.drawRightString(
            right,
            height - 50,
            f"共 {len(events)} 个音符 · 第 {page_index + 1}/{page_count} 页",
        )

        output.setFillColor(HexColor("#201D37"))
        output.setFont(font, 12)
        output.drawString(margin, height - 94, "简谱")
        cell_width = 54
        base_y = height - 132
        for index, event in enumerate(page_events):
            col, row = index % 13, index // 13
            x, y = margin + col * cell_width, base_y - row * 48
            output.setFont(font, 17)
            output.setFillColor(HexColor("#19182B"))
            output.drawCentredString(
                x + 20, y, numbered_name(event.midi).replace("♯", "#")
            )
            output.setFont(font, 7)
            output.setFillColor(HexColor("#7B8496"))
            output.drawCentredString(x + 20, y - 15, duration_name(event.quarter_length))

        output.setFont(font, 12)
        output.setFillColor(HexColor("#201D37"))
        output.drawString(margin, 356, "五线谱")
        draw_staff(page_events[:13], 286)
        if len(page_events) > 13:
            draw_staff(page_events[13:], 150)

        output.setStrokeColor(HexColor("#E1E4EB"))
        output.line(margin, 34, right, 34)
        output.setFont("Helvetica", 7)
        output.setFillColor(HexColor("#8A92A2"))
        output.drawString(margin, 20, "Created with Hum2Score")
        output.drawRightString(right, 20, "hum-to-notation project")
        output.showPage()
    output.save()
