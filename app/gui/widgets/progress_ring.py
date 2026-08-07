"""Circular progress indicator shown above the Projet panel's Launch button.

Two modes, because not every worker reports a percentage:

- **determinate** — an arc fills clockwise to the reported value, with the
  percentage in the middle. Used by COLMAP, 360, Sharp video and Export, the
  four workers that emit ``progress_signal``.
- **indeterminate** — a sweeping arc rotates, YouTube-style, with no number.
  This is what training shows: ``BrushWorker`` reports no percentage at all
  (its engine only gets a ``logger_callback``), and a ring frozen at 0% would
  read as a hung run rather than a working one.

The widget hides itself when idle, so the panel looks unchanged outside a run.
"""

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app.gui.styles import DEFAULT_THEME, THEMES, get_saved_theme

# Resolved at import, like rail.py: styles.py broadcasts no theme-change signal
# that a live widget could subscribe to.
_THEME = THEMES.get(get_saved_theme(), THEMES[DEFAULT_THEME])
_ACCENT = _THEME["accent"]
_TRACK = _THEME["border"]
_TEXT = _THEME["text"]

_SIZE = 52          # outer square, in px
_THICKNESS = 5      # ring stroke width
_SWEEP = 100        # arc length of the indeterminate sweep, in degrees
_STEP = 6           # degrees per animation tick
_INTERVAL = 33      # ms between ticks (~30 fps)


class ProgressRing(QWidget):
    """Round activity indicator. Idle and hidden until :meth:`start` is called."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = None      # None → indeterminate
        self._angle = 0
        self.setFixedSize(_SIZE, _SIZE)
        self.setVisible(False)

        self._timer = QTimer(self)
        self._timer.setInterval(_INTERVAL)
        self._timer.timeout.connect(self._advance)

    # ── Control ─────────────────────────────────────────────────────────────────
    def start(self):
        """Show the ring and begin spinning, with no percentage yet.

        Called when a worker starts rather than when its first progress value
        arrives: COLMAP can spend a long while before reporting anything, and
        that gap is exactly when the user needs to see something is happening.
        """
        self._value = None
        self._angle = 0
        self.setVisible(True)
        self._timer.start()

    def set_value(self, value):
        """Switch to determinate mode and display *value* (0-100)."""
        self._value = max(0, min(100, int(value)))
        self.setVisible(True)
        # The sweep animation would fight the arc for the same pixels.
        self._timer.stop()
        self.update()

    def stop(self):
        self._timer.stop()
        self._value = None
        self._angle = 0
        self.setVisible(False)

    def _advance(self):
        self._angle = (self._angle + _STEP) % 360
        self.update()

    # ── Painting ────────────────────────────────────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        inset = _THICKNESS / 2 + 1
        rect = QRectF(inset, inset, self.width() - 2 * inset, self.height() - 2 * inset)

        pen = QPen(QColor(_TRACK), _THICKNESS)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawEllipse(rect)

        pen.setColor(QColor(_ACCENT))
        painter.setPen(pen)
        # Qt angles are in 1/16th of a degree, 0 at 3 o'clock, counter-clockwise
        # positive — hence starting at 90 (12 o'clock) and sweeping negative to
        # fill clockwise, the direction people read a progress ring.
        if self._value is None:
            painter.drawArc(rect, (90 - self._angle) * 16, -_SWEEP * 16)
        else:
            painter.drawArc(rect, 90 * 16, -int(360 * 16 * self._value / 100))
            font = QFont(self.font())
            font.setPointSizeF(max(9.0, _SIZE * 0.24))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor(_TEXT))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, f"{self._value}%"
            )
