# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for the distributable macOS application."""

from PyInstaller.utils.hooks import collect_all


crepe_datas, crepe_binaries, crepe_hiddenimports = collect_all("crepe")

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=crepe_binaries,
    datas=[
        ("assets/hum2score-icon.png", "assets"),
        ("assets/hum2score-icon.svg", "assets"),
        ("assets/Hum2ScoreTemplate.png", "assets"),
        ("assets/hum2score-menubar.svg", "assets"),
        *crepe_datas,
    ],
    hiddenimports=crepe_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # CREPE only imports matplotlib/imageio in its optional salience-image
    # export branch. Hum2Score never uses that branch; excluding both removes
    # Matplotlib's slow per-launch font-cache runtime hook.
    excludes=["PyQt5", "PySide2", "PySide6", "tkinter", "matplotlib", "imageio"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Hum2Score",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Hum2Score",
)

app = BUNDLE(
    coll,
    name="Hum2Score.app",
    icon="assets/Hum2Score-v042.icns",
    bundle_identifier="com.hum2score.desktop.v042",
    info_plist={
        "CFBundleDisplayName": "Hum2Score",
        "CFBundleName": "Hum2Score",
        "CFBundleShortVersionString": "0.4.2",
        "CFBundleVersion": "6",
        "NSMicrophoneUsageDescription": "Hum2Score 需要访问麦克风，以录制哼唱并识别主旋律。",
        "NSHighResolutionCapable": True,
        # Hum2Score currently ships a purpose-designed light canvas. Keeping
        # Cocoa controls in Aqua prevents an unreadable dark unified titlebar.
        "NSRequiresAquaSystemAppearance": True,
        "LSMinimumSystemVersion": "12.0",
    },
)
