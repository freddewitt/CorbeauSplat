#!/usr/bin/env python3
"""GUI launcher helpers for CorbeauSplat."""
import sys
from pathlib import Path as _Path


def _set_macos_dock_icon(icon_path: _Path):
    try:
        from AppKit import NSApplication, NSImage
        ns_image = NSImage.alloc().initWithContentsOfFile_(str(icon_path))
        if ns_image:
            NSApplication.sharedApplication().setApplicationIconImage_(ns_image)
    except Exception:
        pass


def _launch_gui():
    from PyQt6.QtCore import QTimer
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication

    from app.gui.main_window import ColmapGUI

    app = QApplication(sys.argv)

    assets = _Path(__file__).resolve().parent.parent.parent / "assets"
    png_path  = assets / "icon.png"
    icns_path = assets / "icon.icns"
    icon_file = png_path if png_path.exists() else icns_path
    if icon_file.exists():
        app.setWindowIcon(QIcon(str(icon_file)))

    dock_src = icns_path if icns_path.exists() else png_path
    if dock_src.exists():
        QTimer.singleShot(0, lambda: _set_macos_dock_icon(dock_src))

    window = ColmapGUI()
    window.show()
    sys.exit(app.exec())
