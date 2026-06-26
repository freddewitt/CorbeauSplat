#!/usr/bin/env python3
"""GUI launcher helpers for CorbeauSplat (Windows)."""
import sys
from pathlib import Path as _Path


def _launch_gui():
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication

    from app.gui.main_window import ColmapGUI

    app = QApplication(sys.argv)

    assets = _Path(__file__).resolve().parent.parent.parent / "assets"
    png_path = assets / "icon.png"
    ico_path = assets / "icon.ico"
    icon_file = ico_path if ico_path.exists() else png_path
    if icon_file.exists():
        app.setWindowIcon(QIcon(str(icon_file)))

    window = ColmapGUI()
    window.show()
    sys.exit(app.exec())
