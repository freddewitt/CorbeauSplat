"""Shared fixtures and PyQt6 mocking for the entire test suite.

Patches PyQt6 at session scope to allow QThread-based worker tests
to import and run without a display or real PyQt6 installation.
"""
import sys
from unittest.mock import MagicMock


class _MockQThread:
    """Stand-in for QThread — plain class avoids MagicMock metaclass issues."""
    def __init__(self):      pass
    def start(self):         pass
    def quit(self):          pass
    def wait(self, *args):   pass
    def isRunning(self):     return False
    def requestInterruption(self): pass
    def isInterruptionRequested(self): return False


class _PyQtSignalMeta(type):
    """Metaclass: pyqtSignal mock is isinstance-able and callable."""
    def __instancecheck__(cls, other):
        return isinstance(other, MagicMock)
    def __call__(cls, *args, **kwargs):
        return MagicMock()


class _MockPyQtSignal(metaclass=_PyQtSignalMeta):
    """Stand-in for pyqtSignal — a class, not a MagicMock instance."""


def _patch_pyqt6():
    """Patch PyQt6 into sys.modules with proper class mocks."""
    if "PyQt6" in sys.modules and not isinstance(sys.modules["PyQt6"], MagicMock):
        return  # Real PyQt6 is installed, don't interfere

    class _PyQt6Module:
        pass

    pyqt6 = _PyQt6Module()
    qtcore = MagicMock()
    qtcore.QTimer = MagicMock()
    qtcore.pyqtSignal = _MockPyQtSignal
    qtcore.QThread = _MockQThread
    pyqt6.QtCore = qtcore
    pyqt6.QtWidgets = MagicMock()
    pyqt6.QtGui = MagicMock()

    sys.modules.setdefault("PyQt6", pyqt6)
    sys.modules.setdefault("PyQt6.QtCore", qtcore)
    sys.modules.setdefault("PyQt6.QtWidgets", pyqt6.QtWidgets)
    sys.modules.setdefault("PyQt6.QtGui", pyqt6.QtGui)

    if "send2trash" not in sys.modules:
        sys.modules["send2trash"] = MagicMock()

    try:
        import numpy  # noqa: F401,F811 — prevent mocking if real numpy is available (plyfile needs it)
    except ImportError:
        # Headless CI without numpy — provide a mock so ply_cleaner.py can import
        sys.modules["numpy"] = MagicMock()


_patch_pyqt6()
