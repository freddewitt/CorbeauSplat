"""Every panel's state must survive a save/load cycle, under a real Qt.

Complements test_gui_config_roundtrip.py, which covers one setting in depth.
This one is broad: it perturbs every combo and checkbox in every panel, saves
the configuration, reloads it into a fresh window and compares the states key
by key.

The bug class it targets is silent: ChainConfig copies get_state() verbatim, so
a key that get_state() produces but set_state() ignores is lost on reload with
nothing failing. The AST contracts in test_panel_contracts.py cannot see it,
and the session-wide PySide6 mock means panels cannot be instantiated for real
anywhere else — hence the subprocess.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_SCRIPT = '''
import json, pathlib, tempfile, warnings
warnings.simplefilter("ignore")
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QSpinBox

app = QApplication([])
tmp = pathlib.Path(tempfile.mkdtemp())

with patch("app.core.config_io.resolve_project_root", return_value=tmp):
    from app.core.config_io import load_config, save_config
    from app.gui.studio_window import StudioWindow

    def perturb(panel):
        """Move every widget off its default so equality is not trivially true.

        Signals are blocked throughout: toggling a checkbox here would fire the
        panel's own handlers, and some of those start worker threads. We are
        testing serialisation, not the handlers.
        """
        for zone in ("center", "right"):
            w = getattr(panel, zone, None)
            if w is None:
                continue
            widgets = (w.findChildren(QComboBox) + w.findChildren(QCheckBox)
                       + w.findChildren(QSpinBox))
            for widget in widgets:
                widget.blockSignals(True)
            try:
                for combo in w.findChildren(QComboBox):
                    # UpscalePanel.combo_model is skipped on purpose. Selecting a
                    # model that is not installed starts a download immediately
                    # (_on_model_changed), and set_state() goes through the same
                    # path — so reloading a saved configuration can kick off a
                    # network transfer. Perturbing it here would make this test
                    # spawn that worker; the behaviour itself is reported in
                    # manifest.md rather than hidden.
                    if combo is getattr(panel, "combo_model", None):
                        continue
                    if combo.count() > 1:
                        combo.setCurrentIndex((combo.currentIndex() + 1) % combo.count())
                for box in w.findChildren(QCheckBox):
                    box.setChecked(not box.isChecked())
                for spin in w.findChildren(QSpinBox):
                    if spin.value() < spin.maximum():
                        spin.setValue(spin.value() + 1)
            finally:
                for widget in widgets:
                    widget.blockSignals(False)

    source = StudioWindow()
    # The OUTILS "brush" panel is a second EntrainementPanel in standalone mode.
    # collect_config() deliberately serialises only the pipeline one, so the
    # standalone instance has no slot in ChainConfig and cannot round trip.
    SERIALISED = {"source", "extraction360", "upscale", "reconstruction",
                  "entrainement", "nettoyage", "export"}
    keys = [k for k, p in source.panels.items()
            if hasattr(p, "get_state") and k in SERIALISED]
    for k in keys:
        perturb(source.panels[k])

    before = {k: source.panels[k].get_state() for k in keys}
    save_config("all_panels", source.collect_config())

    fresh = StudioWindow()
    fresh.apply_config(load_config("all_panels"))
    after = {k: fresh.panels[k].get_state() for k in keys}

    report = {}
    for k in keys:
        lost = sorted(key for key in before[k]
                      if before[k][key] != after[k].get(key))
        report[k] = {"keys": len(before[k]), "mismatched": lost}

    print("REPORT=" + json.dumps(report))
'''


@pytest.fixture(scope="module")
def report():
    env = {
        "QT_QPA_PLATFORM": "offscreen",
        "PATH": "/usr/bin:/bin",
        "HOME": str(Path.home()),
        "PYTHONPATH": str(PROJECT_ROOT),
    }
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        capture_output=True, text=True, timeout=180,
        cwd=str(PROJECT_ROOT), env=env,
    )
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("REPORT=")), None)
    if line is None:
        if "No module named 'PySide6'" in proc.stderr:
            pytest.skip("real PySide6 not importable in this environment")
        pytest.fail(f"real-Qt subprocess produced no report:\n{proc.stderr[-2000:]}")
    # The report is what matters. Qt routinely aborts at interpreter exit with
    # "QThread: Destroyed while thread is still running" — a teardown artefact
    # of windows that own workers, long after the measurements are taken.
    return json.loads(line.removeprefix("REPORT="))


def test_all_serialised_panels_are_covered(report):
    """A panel gaining a ChainConfig slot must be exercised here, not skipped."""
    assert set(report) == {
        "source", "extraction360", "upscale", "reconstruction",
        "entrainement", "nettoyage", "export",
    }


def test_no_panel_reports_an_empty_state(report):
    empty = [name for name, data in report.items() if data["keys"] == 0]
    assert empty == [], f"panels exposing no state: {empty}"


@pytest.mark.parametrize("panel", [
    "source", "extraction360", "upscale", "reconstruction",
    "entrainement", "nettoyage", "export",
])
def test_panel_state_survives_save_and_reload(report, panel):
    """Every key get_state() produces must come back identical after a reload."""
    mismatched = report[panel]["mismatched"]
    assert mismatched == [], (
        f"{panel}: {len(mismatched)} key(s) lost or altered by the save/load "
        f"cycle: {mismatched}"
    )
