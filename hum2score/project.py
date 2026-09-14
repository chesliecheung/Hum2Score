"""Portable .hum2score project persistence."""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import asdict
from pathlib import Path

import numpy as np

from .models import NoteEvent
from .pitch import PitchTrack


def save_project(
    path: str | Path,
    events: list[NoteEvent],
    audio: np.ndarray | None,
    sample_rate: int,
    track: PitchTrack | None,
    smooth_midi: np.ndarray | None,
) -> None:
    manifest = {
        "format": "hum2score-project",
        "version": 1,
        "sample_rate": int(sample_rate),
        "notes": [asdict(event) for event in events],
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("project.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        if audio is not None:
            buffer = io.BytesIO()
            np.save(buffer, np.asarray(audio, dtype=np.float32), allow_pickle=False)
            archive.writestr("audio.npy", buffer.getvalue())
        if track is not None:
            buffer = io.BytesIO()
            np.savez_compressed(
                buffer,
                times=track.times,
                frequencies=track.frequencies,
                confidences=track.confidences,
                smooth=np.asarray(smooth_midi) if smooth_midi is not None else np.array([]),
            )
            archive.writestr("pitch.npz", buffer.getvalue())


def load_project(
    path: str | Path,
) -> tuple[list[NoteEvent], np.ndarray | None, int, PitchTrack | None, np.ndarray | None]:
    with zipfile.ZipFile(path, "r") as archive:
        manifest = json.loads(archive.read("project.json"))
        if manifest.get("format") != "hum2score-project":
            raise ValueError("这不是有效的 Hum2Score 工程文件。")
        events = [NoteEvent(**item) for item in manifest.get("notes", [])]
        audio = None
        if "audio.npy" in archive.namelist():
            audio = np.load(io.BytesIO(archive.read("audio.npy")), allow_pickle=False)
        track = smooth = None
        if "pitch.npz" in archive.namelist():
            data = np.load(io.BytesIO(archive.read("pitch.npz")), allow_pickle=False)
            track = PitchTrack(data["times"], data["frequencies"], data["confidences"])
            smooth = data["smooth"]
            if smooth.size == 0:
                smooth = None
        return events, audio, int(manifest.get("sample_rate", 16000)), track, smooth

