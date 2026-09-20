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
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from app.gui.studio_window import StudioWindow

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

    window = StudioWindow()
    window.show()

    # The CLI has always warned about missing dependencies; the GUI never ran
    # the check at all, so a user without Brush or ffmpeg only found out when a
    # run failed. Reported into the run log rather than a startup dialog: most
    # entries are per-feature and harmless for someone not using that feature.
    # Deferred to after show() because check_dependencies() probes ffmpeg in a
    # subprocess — ~90 ms typically, capped at the 5 s timeout it passes.
    QTimer.singleShot(0, lambda: _report_missing_dependencies(window))

    sys.exit(app.exec())


def _report_missing_dependencies(window):
    from app.core.system import check_dependencies

    try:
        missing = check_dependencies()
    except Exception:
        return
    if not missing:
        return

    message = "⚠️ Dépendances manquantes : " + ", ".join(missing)
    logs_window = getattr(window, "logs_window", None)
    if logs_window is not None:
        logs_window.append_log(message)
