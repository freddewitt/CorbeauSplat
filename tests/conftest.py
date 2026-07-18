"""Shared fixtures and PySide6 mocking for the entire test suite.

Patches PySide6 at session scope to allow QThread-based worker tests
to import and run without a display or real PySide6 installation.
"""
import os
import sys
from unittest.mock import MagicMock

# pytest-qt : force le binding PySide6
os.environ.setdefault("PYTEST_QT_API", "pyside6")


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
    """Metaclass: Signal mock is isinstance-able and callable."""
    def __instancecheck__(cls, other):
        return isinstance(other, MagicMock)
    def __call__(cls, *args, **kwargs):
        return MagicMock()


class _MockPyQtSignal(metaclass=_PyQtSignalMeta):
    """Stand-in for Signal — a class, not a MagicMock instance."""


def _patch_pyqt6():
    """Patch PySide6 into sys.modules with proper class mocks."""
    if "PySide6" in sys.modules and not isinstance(sys.modules["PySide6"], MagicMock):
        return  # Real PySide6 is installed, don't interfere

    class _PySide6Module:
        pass

    pyqt6 = _PySide6Module()
    qtcore = MagicMock()
    qtcore.QTimer = MagicMock()
    qtcore.Signal = _MockPyQtSignal
    qtcore.QThread = _MockQThread
    pyqt6.QtCore = qtcore
    pyqt6.QtWidgets = MagicMock()
    pyqt6.QtGui = MagicMock()

    sys.modules.setdefault("PySide6", pyqt6)
    sys.modules.setdefault("PySide6.QtCore", qtcore)
    sys.modules.setdefault("PySide6.QtWidgets", pyqt6.QtWidgets)
    sys.modules.setdefault("PySide6.QtGui", pyqt6.QtGui)

    if "send2trash" not in sys.modules:
        sys.modules["send2trash"] = MagicMock()

    try:
        import numpy  # noqa: F401,F811 — prevent mocking if real numpy is available (plyfile needs it)
    except ImportError:
        # Headless CI without numpy — provide a mock so ply_cleaner.py can import
        sys.modules["numpy"] = MagicMock()


_patch_pyqt6()
