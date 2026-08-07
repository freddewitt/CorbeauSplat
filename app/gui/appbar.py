"""Minimal top title bar of the Studio window: app icon + name + version.

This is intentionally NOT a revival of the old functional TopBar (no fields,
no combos, no business actions — those now live in ``SourcePanel`` and the
bottom bar). It is a plain, always-visible header row placed above the
rail/center/right body, giving the window a clear identity at a glance.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from app import VERSION
from app.core.system import resolve_project_root

_ICON_PX = 20


class AppBar(QWidget):
    """Always-visible header: app icon, name (hardcoded, not i18n — it's a
    proper noun) and version, read from ``app.VERSION``."""

    def __init__(self, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 4, 10, 4)
        row.setSpacing(8)

        icon_path = resolve_project_root() / "assets" / "icon.icns"
        pixmap = QPixmap(str(icon_path))
        # Loading a .icns via QPixmap is macOS-specific and can silently fail
        # in a headless environment: show nothing rather than a broken
        # placeholder or an exception.
        if not pixmap.isNull():
            lbl_icon = QLabel()
            lbl_icon.setPixmap(
                pixmap.scaled(
                    _ICON_PX,
                    _ICON_PX,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            row.addWidget(lbl_icon)

        lbl_name = QLabel("CorbeauSplat")
        lbl_name.setStyleSheet("font-weight: bold;")
        row.addWidget(lbl_name)

        lbl_version = QLabel(f"v{VERSION}")
        lbl_version.setStyleSheet("color: #666666; font-size: 10px;")
        row.addWidget(lbl_version)

        row.addStretch(1)
