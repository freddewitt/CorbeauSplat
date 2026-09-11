"""Regression tests for the standalone Reconstruction "Lancer" button chaining
into Brush when "Run Brush" (``run_state.entrainement_apres``) is checked.

Bug: the Reconstruction panel's own local Lancer button never chained into
subsequent pipeline steps (unlike the global Source-tab Lancer), so the
"Run Brush" checkbox visible in that same panel silently did nothing when
that button was used. Fixed via ``StudioWindow._on_reconstruction_standalone_finished``.
"""
import sys
from unittest.mock import MagicMock

from tests.conftest import _patch_pyqt6

_patch_pyqt6()

# StudioWindow(QMainWindow) must stay a real, instantiable Python class (for
# __new__/__init__ like the workers tested elsewhere) under the session-wide
# PySide6 mock — QtWidgets is a generic MagicMock whose attributes aren't
# usable as a base class. Only QMainWindow is patched, before studio_window's
# first import — same pattern as test_tool_launch_integration.py.
sys.modules["PySide6.QtWidgets"].QMainWindow = type("QMainWindow", (), {})

from app.core.run_state import RunState  # noqa: E402
from app.gui import studio_window as sw  # noqa: E402


def _make_window():
    window = sw.StudioWindow.__new__(sw.StudioWindow)
    window.run_state = RunState()
    window._launch_entrainement = MagicMock()
    return window


class TestReconstructionStandaloneChaining:
    def test_chains_into_brush_when_flag_set_and_success(self):
        window = _make_window()
        window.run_state.entrainement_apres = True

        window._on_reconstruction_standalone_finished(True, "ok")

        window._launch_entrainement.assert_called_once()

    def test_does_not_chain_when_flag_unset(self):
        window = _make_window()
        window.run_state.entrainement_apres = False

        window._on_reconstruction_standalone_finished(True, "ok")

        window._launch_entrainement.assert_not_called()

    def test_does_not_chain_when_reconstruction_failed(self):
        window = _make_window()
        window.run_state.entrainement_apres = True

        window._on_reconstruction_standalone_finished(False, "erreur")

        window._launch_entrainement.assert_not_called()
