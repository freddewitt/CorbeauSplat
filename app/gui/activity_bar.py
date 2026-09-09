"""Activity bar, at the bottom of the Studio window.

Replaces the former ``LogBar``. The log is no longer here — it has its own
window (``logs_window.py``), opened by a button on the bottom bar. What
remains is only what should be visible at all times without opening anything:

    Reconstruction   Feature extraction: image 42/210   [████░░ 42%]

Cancel is no longer here either: it lives under each panel's Launch button
(``widgets/cancel_button.py``), next to the action it interrupts.

- **the current step** (rail label, already translated);
- **the detail** of what it's doing right now: the last line reported by the
  worker, elided in the middle — file paths all look alike from the left, it's
  the end that identifies the line;
- **the progress**, only for workers that emit one. COLMAP, 360, video Sharp
  and Export do; Brush training does not (its engine only receives a
  ``logger_callback``), hence a hidden bar in that case rather than a bar
  stuck at 0% that would suggest a freeze.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QWidget,
)

from app.core.i18n import add_language_observer
from app.gui.styles import DEFAULT_THEME, THEMES, get_saved_theme

# Resolved at import time, as in rail.py: styles.py doesn't broadcast a theme
# change signal that a live widget could subscribe to.
_MUTED = THEMES.get(get_saved_theme(), THEMES[DEFAULT_THEME])["muted"]


class ActivityBar(QWidget):
    """Current step + detail + progress. Always visible, no action."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._detail = ""
        self.init_ui()
        add_language_observer(self.retranslate_ui)

    def init_ui(self):
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 4, 10, 4)
        row.setSpacing(10)

        self.lbl_step = QLabel()
        self.lbl_step.setStyleSheet("font-weight: 600; background: transparent;")
        row.addWidget(self.lbl_step)

        self.lbl_detail = QLabel()
        self.lbl_detail.setStyleSheet(f"color: {_MUTED}; background: transparent;")
        self.lbl_detail.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        row.addWidget(self.lbl_detail, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setFixedWidth(180)
        self.progress.setVisible(False)
        row.addWidget(self.progress)

    # ── Step and detail ─────────────────────────────────────────────────────────
    def set_step(self, label):
        """Current step, label already translated (cf. ``rail.item_label``)."""
        self.lbl_step.setText(str(label or ""))

    def set_activity(self, message):
        """Current detail. Wired to both ``log_signal`` and ``status_signal``:
        ``BrushWorker`` only emits the former, sticking to status would leave
        training with no visible feedback at all."""
        text = str(message or "").strip()
        self._detail = text.splitlines()[-1] if text else ""
        self._refresh_detail()

    def _refresh_detail(self):
        fm = self.lbl_detail.fontMetrics()
        width = max(120, self.lbl_detail.width())
        self.lbl_detail.setText(
            fm.elidedText(self._detail, Qt.TextElideMode.ElideMiddle, width)
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_detail()

    # ── Progress ─────────────────────────────────────────────────────────────────
    def set_progress(self, value):
        self.progress.setVisible(True)
        self.progress.setValue(max(0, min(100, int(value))))

    def reset_activity(self):
        """End of run: no leftover label, no bar stuck on its last value."""
        self._detail = ""
        self.lbl_step.clear()
        self.lbl_detail.clear()
        self.progress.setValue(0)
        self.progress.setVisible(False)

    def retranslate_ui(self):
        """Nothing to retranslate today: the step and detail are pushed already
        translated by ``StudioWindow``. Kept so this stays subscribable to
        language changes if a fixed label shows up here."""
