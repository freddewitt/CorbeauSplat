"""Named-configuration round trip, against a real Qt, in a subprocess.

The suite installs a session-wide PySide6 mock (tests/conftest.py), which is
process-global and cannot be undone mid-run. Panels therefore cannot be
instantiated for real anywhere else, and the AST contracts in
test_panel_contracts.py only prove a widget is populated and read — not that
its value survives save/load.

A subprocess with the real PySide6 offscreen closes that gap. Every scenario
runs in a *single* launch and the assertions parse its output: a launch costs
roughly a second, and four of them would have doubled the suite's runtime for
no extra coverage.

The gap is worth closing because ChainConfig.source copies get_state()
verbatim, so a key missing from either side is silently lost on reload, with
no failure anywhere to point at it.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_SCENARIOS = '''
import json, pathlib, tempfile, warnings
warnings.simplefilter("ignore")
from unittest.mock import patch
from PySide6.QtWidgets import QApplication

app = QApplication([])
tmp = pathlib.Path(tempfile.mkdtemp())
results = {}

with patch("app.core.config_io.resolve_project_root", return_value=tmp):
    from app.core.config_io import load_config, save_config
    from app.core.params import ColmapParams
    from app.gui.panels.reconstruction_logic import apply_source_settings
    from app.gui.studio_window import StudioWindow

    def reopen(name):
        """A fresh window, as if the app had been restarted."""
        w = StudioWindow()
        w.apply_config(load_config(name))
        return w

    # jpeg: chosen, saved, reopened
    w = StudioWindow()
    results["default"] = w.panels["source"].combo_convert.currentData()
    w.panels["source"].combo_convert.setCurrentIndex(1)
    path = pathlib.Path(save_config("rt_jpeg", w.collect_config()))
    results["on_disk"] = json.loads(path.read_text())["source"].get("convert")
    back = reopen("rt_jpeg")
    results["jpeg"] = back.panels["source"].combo_convert.currentData()
    results["jpeg_params"] = apply_source_settings(
        ColmapParams(), back.panels["source"].get_state()
    ).image_convert_format

    # off: the value that actually changes behaviour
    w = StudioWindow()
    w.panels["source"].combo_convert.setCurrentIndex(2)
    save_config("rt_off", w.collect_config())
    results["off"] = reopen("rt_off").panels["source"].combo_convert.currentData()

    # a config written before the widget existed
    legacy = json.loads(path.read_text())
    legacy["source"].pop("convert", None)
    path.write_text(json.dumps(legacy))
    results["legacy"] = reopen("rt_jpeg").panels["source"].combo_convert.currentData()

print("RESULTS=" + json.dumps(results))
'''


@pytest.fixture(scope="module")
def results():
    """Run every scenario once under real Qt, return the parsed outcome."""
    env = {
        "QT_QPA_PLATFORM": "offscreen",
        "PATH": "/usr/bin:/bin",
        "HOME": str(Path.home()),
    }
    proc = subprocess.run(
        [sys.executable, "-c", _SCENARIOS],
        capture_output=True, text=True, timeout=180,
        cwd=str(PROJECT_ROOT), env=env,
    )
    if proc.returncode != 0:
        if "No module named 'PySide6'" in proc.stderr:
            pytest.skip("real PySide6 not importable in this environment")
        pytest.fail(f"real-Qt subprocess failed:\n{proc.stderr[-2000:]}")

    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("RESULTS=")), None)
    assert line, f"no results emitted:\n{proc.stdout[-2000:]}"
    return json.loads(line.removeprefix("RESULTS="))


def test_default_is_png(results):
    assert results["default"] == "png"


def test_choice_is_written_to_the_config_file(results):
    assert results["on_disk"] == "jpeg"


def test_jpeg_comes_back_after_reopening(results):
    assert results["jpeg"] == "jpeg"


def test_reloaded_value_reaches_colmap_params(results):
    """A restored widget is only useful if the engine receives the value."""
    assert results["jpeg_params"] == "jpeg"


def test_off_round_trips(results):
    assert results["off"] == "off"


def test_config_saved_before_the_widget_falls_back_to_png(results):
    assert results["legacy"] == "png"
