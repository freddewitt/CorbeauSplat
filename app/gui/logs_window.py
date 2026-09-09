"""Dedicated window for the execution log.

The log used to occupy the bottom of the main window, collapsed by default:
unreadable once expanded (a few lines tall), and it crowded out the screen
content when opened. It now lives in its own window, **non-modal** — it can
stay open during a run while work continues in the Studio.

The content IS a ``LogsTab``, like the old bar: search, copy, save and the
auto-scroll lock are already in place there, nothing to reimplement.
"""

from PySide6.QtWidgets import QDialog, QVBoxLayout

from app.core.i18n import add_language_observer, tr
from app.gui.tabs.logs_tab import LogsTab


class LogsWindow(QDialog):
    """Full log, opened on demand from the bottom bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Non-modal: a run can last hours, blocking the Studio while
        # reading its logs would make no sense.
        self.setModal(False)
        self.resize(900, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.logs = LogsTab()
        layout.addWidget(self.logs)

        add_language_observer(self.retranslate_ui)
        self.retranslate_ui()

    # ── Delegation to the embedded LogsTab ──────────────────────────────────────
    def append_log(self, message):
        """Fed continuously, whether the window is visible or not.

        This is deliberate: the full run history must be there on first
        opening, including whatever happened before anyone thought to look.
        """
        self.logs.append_log(message)

    def clear_log(self):
        self.logs.clear_log()

    def show_logs(self, search: str = ""):
        """Show the window (and bring it to front if already open)."""
        self.show()
        self.raise_()
        self.activateWindow()
        if search:
            self.logs.search_input.setText(search)
            self.logs._find_next()

    def retranslate_ui(self):
        self.setWindowTitle(tr("logbar_title", "Logs"))
