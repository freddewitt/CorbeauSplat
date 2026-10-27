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
- **the progress**, only for workers that emit one: COLMAP, 360, video Sharp,
  Export and Brush training (parsed from its own bar, see ``live_progress``).
  The bar glides between updates (``SmoothValue``) instead of jumping;
- **the time left**, when the tool reports a rate (Brush today).
"""

import time

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
from app.gui.widgets.smooth_value import SmoothValue

# The bar works in tenths of a percent so the glide has room to move.
_SCALE = 10
# Brush's rate wobbles between redraws; refreshing the estimate this often
# keeps it readable instead of flickering.
_ETA_REFRESH_S = 2.0


def format_eta(seconds: float) -> str:
    """Short, language-neutral remaining time: "< 1 min", "~12 min", "~1 h 05"."""
    if seconds < 60:
        return "< 1 min"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"~{minutes} min"
    return f"~{minutes // 60} h {minutes % 60:02d}"


class ActivityBar(QWidget):
    """Current step + detail + progress. Always visible, no action."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._detail = ""
        self._eta_shown_at = 0.0
        self.init_ui()
        self._smooth = SmoothValue(self._show_progress, self)
        add_language_observer(self.retranslate_ui)

    def init_ui(self):
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 4, 10, 4)
        row.setSpacing(10)

        self.lbl_step = QLabel()
        self.lbl_step.setStyleSheet("font-weight: 600; background: transparent;")
        row.addWidget(self.lbl_step)

        self.lbl_detail = QLabel()
        muted = THEMES.get(get_saved_theme(), THEMES[DEFAULT_THEME])["muted"]
        self.lbl_detail.setStyleSheet(f"color: {muted}; background: transparent;")
        self.lbl_detail.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        row.addWidget(self.lbl_detail, 1)

        self.lbl_eta = QLabel()
        self.lbl_eta.setStyleSheet(f"color: {muted}; background: transparent;")
        self.lbl_eta.setVisible(False)
        row.addWidget(self.lbl_eta)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100 * _SCALE)
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
    def _show_progress(self, value):
        self.progress.setValue(round(value * _SCALE))
        # Whole percent, floored like the ring: 99.9 must not read "100%".
        self.progress.setFormat(f"{int(value)}%")

    def set_progress(self, value):
        self.progress.setVisible(True)
        value = max(0.0, min(100.0, float(value)))
        if value < self._smooth.value or value >= 100:
            # A new step started over, or this one is done: the time estimate
            # no longer applies.
            self.set_eta(-1)
        self._smooth.set_target(value)

    def set_eta(self, seconds):
        """Time left in the current step; negative hides it."""
        if seconds is None or seconds < 0:
            self.lbl_eta.clear()
            self.lbl_eta.setVisible(False)
            self._eta_shown_at = 0.0
            return
        now = time.monotonic()
        if self.lbl_eta.isVisible() and now - self._eta_shown_at < _ETA_REFRESH_S:
            return
        self._eta_shown_at = now
        self.lbl_eta.setText(format_eta(seconds))
        self.lbl_eta.setVisible(True)

    def reset_activity(self):
        """End of run: no leftover label, no bar stuck on its last value."""
        self._detail = ""
        self.lbl_step.clear()
        self.lbl_detail.clear()
        self._smooth.snap(0)
        self.set_eta(-1)
        self.progress.setVisible(False)

    def retranslate_ui(self):
        """Nothing to retranslate today: the step and detail are pushed already
        translated by ``StudioWindow``. Kept so this stays subscribable to
        language changes if a fixed label shows up here."""
