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
    # run failed. Deferred to after show() because check_dependencies() probes
    # ffmpeg in a subprocess — ~90 ms typically, capped at the 5 s timeout.
    QTimer.singleShot(0, lambda: _report_missing_dependencies(window))

    sys.exit(app.exec())


def _report_missing_dependencies(window):
    """Log every missing dependency, and raise a dialog for the core ones.

    Two tiers on purpose. A missing per-feature binary (Glomap, Upscayl) only
    matters to someone about to use that feature, so it goes to the log. A
    missing core tool (ffmpeg, COLMAP, send2trash) breaks every pipeline, and
    silently letting the user reach a failed run is what this check exists to
    prevent — that one interrupts.
    """
    from app.core.system import check_dependencies

    try:
        missing = check_dependencies()
    except Exception:
        return
    if not missing:
        return

    logs_window = getattr(window, "logs_window", None)
    if logs_window is not None:
        logs_window.append_log("⚠️ Dépendances manquantes : " + ", ".join(missing))

    # Feature entries carry a "name (feature)" label; core ones are bare.
    core_missing = [name for name in missing if "(" not in name]
    if not core_missing:
        return

    from PySide6.QtWidgets import QMessageBox

    from app.core.i18n import tr

    box = QMessageBox(window)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(tr("deps_missing_title", "Dépendances manquantes"))
    box.setText(
        tr("deps_missing_body", "Ces outils sont requis et introuvables :")
        + "\n\n• " + "\n• ".join(core_missing)
    )
    box.setInformativeText(
        tr("deps_missing_hint",
           "Relancez l'installateur de dépendances avant de démarrer un traitement.")
    )
    box.exec()
