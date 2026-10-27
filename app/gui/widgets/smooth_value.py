"""A number that glides to its target instead of jumping.

Progress arrives in bursts: Brush's bar every few hundred ms, COLMAP once per
image or block, sometimes seconds apart. Setting a bar straight to each value
makes it stutter even when the updates are frequent. ``SmoothValue`` eases the
displayed value toward the latest target, and the widget repaints from
``value``. Going backwards (a new step starting at 0) snaps immediately: an
animated rewind would read as lost work.
"""

from collections.abc import Callable

from PySide6.QtCore import QEasingCurve, QObject, QVariantAnimation

_DURATION_MS = 450


class SmoothValue(QObject):
    def __init__(self, on_change: Callable[[float], None], parent=None):
        super().__init__(parent)
        self._on_change = on_change
        self.value = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(_DURATION_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._step)

    def set_target(self, target: float) -> None:
        target = float(target)
        if target <= self.value:
            self.snap(target)
            return
        # Restarting from the current displayed value keeps the motion
        # continuous when updates arrive faster than the animation.
        self._anim.stop()
        self._anim.setStartValue(self.value)
        self._anim.setEndValue(target)
        self._anim.start()

    def snap(self, target: float) -> None:
        self._anim.stop()
        self._step(float(target))

    def _step(self, value) -> None:
        self.value = float(value)
        self._on_change(self.value)
