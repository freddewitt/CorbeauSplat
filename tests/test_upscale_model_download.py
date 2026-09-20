"""Selecting an Upscayl model must not download behind the user's back.

`_on_model_changed` used to be wired to `currentIndexChanged`, which fires on
`setCurrentIndex()` as well — the call `set_state()` makes. Reloading a saved
configuration that named an uninstalled model therefore started a network
transfer the user never asked for, and `refresh_models()` rebuilding the combo
could trigger it too.

Runs against a real Qt in a subprocess: the suite's session-wide PySide6 mock
is process-global, so a real panel cannot be built anywhere else.
"""
from pathlib import Path

import pytest

from tests._real_qt import run_for_payload

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_SCRIPT = '''
import json, warnings
warnings.simplefilter("ignore")
from unittest.mock import patch
from PySide6.QtWidgets import QApplication

app = QApplication([])
from app.core.run_state import RunState
from app.gui.panels.upscale_panel import UpscalePanel

results = {}
with patch("app.upscayl_models.UpscaylModel.is_downloaded", return_value=False):
    with patch("app.gui.widgets.upscale_widgets.ModelDownloadWorker") as worker:
        panel = UpscalePanel(RunState())
        results["on_build"] = worker.called

        worker.reset_mock()
        panel.set_state({"model_id": panel.combo_model.itemData(1)})
        results["on_set_state"] = worker.called
        results["status_after_set_state"] = panel.lbl_status.text()

        worker.reset_mock()
        panel.refresh_models()
        results["on_refresh"] = worker.called

        worker.reset_mock()
        panel.combo_model.setCurrentIndex(2)
        panel.combo_model.activated.emit(2)
        results["on_user_pick"] = worker.called

    # An installed model must not be downloaded even when the user picks it.
    with patch("app.upscayl_models.UpscaylModel.is_downloaded", return_value=True):
        with patch("app.gui.widgets.upscale_widgets.ModelDownloadWorker") as worker2:
            panel2 = UpscalePanel(RunState())
            panel2.combo_model.setCurrentIndex(1)
            panel2.combo_model.activated.emit(1)
            results["installed_on_user_pick"] = worker2.called

print("RESULTS=" + json.dumps(results))
'''


@pytest.fixture(scope="module")
def results():
    """Run every scenario once under real Qt; see tests/_real_qt.py."""
    return run_for_payload(_SCRIPT, marker="RESULTS=")


def test_building_the_panel_downloads_nothing(results):
    assert results["on_build"] is False


def test_restoring_a_configuration_downloads_nothing(results):
    """The reported bug: set_state() reached the network."""
    assert results["on_set_state"] is False


def test_refreshing_the_list_downloads_nothing(results):
    assert results["on_refresh"] is False


def test_restoring_still_reports_the_missing_model(results):
    """Silence would only move the surprise to the moment the run fails."""
    assert "4xLSDIR" in results["status_after_set_state"]


def test_user_picking_an_uninstalled_model_downloads(results):
    """The feature itself must survive: an explicit choice still fetches."""
    assert results["on_user_pick"] is True


def test_user_picking_an_installed_model_downloads_nothing(results):
    assert results["installed_on_user_pick"] is False
