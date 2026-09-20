"""Every panel, built for real and exercised through its public contract.

The AST contracts in test_panel_contracts.py check the source; this builds the
panels under a real Qt and calls what StudioWindow calls: get_params(),
get_state()/set_state(), retranslate_ui() in all nine locales, and the small
predicates. Panels sat at 9-14% coverage because none of that had ever run in
a test (audit M4).

retranslate_ui() across every locale is the high-value part: it is where a
missing key or a format placeholder that does not match its arguments shows
up, and nothing else in the suite exercises the panels' own tr() calls.

Runs in a subprocess, since the suite's PySide6 mock is process-global. The
language switch is neutered there: set_language() persists to the user's real
config.json, which a test must never touch.
"""
from pathlib import Path

import pytest

from tests._real_qt import run_for_payload

PROJECT_ROOT = Path(__file__).resolve().parent.parent

PANELS = ("source", "extraction360", "upscale", "reconstruction", "entrainement",
          "nettoyage", "export", "visualiser", "brush", "sharp", "supersplat",
          "splattransform", "4dgs")

_SCRIPT = '''
import json, traceback, warnings
warnings.simplefilter("ignore")
from PySide6.QtWidgets import QApplication

app = QApplication([])

import app.core.i18n as i18n
# set_language() writes to the user's config.json. Neutered before anything
# calls it: a test must never leave the app in another language.
i18n._lm.save_config = lambda *a, **k: None

from app.core.run_state import RunState
from app.gui.studio_window import StudioWindow

LOCALES = ["fr", "en", "de", "es", "it", "ja", "ru", "zh", "ar"]
report = {}
window = StudioWindow()

for key, panel in window.panels.items():
    entry = {"built": True, "errors": []}

    for name in ("get_params", "get_state"):
        fn = getattr(panel, name, None)
        if fn is None:
            continue
        try:
            value = fn()
            entry[name] = sorted(value) if isinstance(value, dict) else type(value).__name__
        except Exception as e:
            entry["errors"].append(f"{name}: {e!r}")

    if hasattr(panel, "get_state") and hasattr(panel, "set_state"):
        try:
            before = panel.get_state()
            panel.set_state(before)
            entry["roundtrip_stable"] = panel.get_state() == before
        except Exception as e:
            entry["errors"].append(f"set_state: {e!r}")

    for predicate in ("is_batch", "is_video", "is_running", "current_mode",
                      "get_format", "get_scale"):
        fn = getattr(panel, predicate, None)
        if fn is None:
            continue
        try:
            fn()
        except Exception as e:
            entry["errors"].append(f"{predicate}: {e!r}")

    if hasattr(panel, "retranslate_ui"):
        for lang in LOCALES:
            try:
                i18n.set_language(lang)
                panel.retranslate_ui()
            except Exception as e:
                entry["errors"].append(f"retranslate_ui[{lang}]: {e!r}")
        i18n.set_language("en")

    report[key] = entry

print("REPORT=" + json.dumps(report))
'''


@pytest.fixture(scope="module")
def report():
    """Run every scenario once under real Qt; see tests/_real_qt.py."""
    return run_for_payload(_SCRIPT, marker="REPORT=")


def test_every_panel_is_covered(report):
    """A new panel must be exercised here, not silently skipped."""
    assert set(report) == set(PANELS)


@pytest.mark.parametrize("panel", PANELS)
def test_panel_contract_raises_nothing(report, panel):
    """Build, read params and state, switch through 9 locales, call predicates."""
    errors = report[panel]["errors"]
    assert errors == [], f"{panel}: " + "; ".join(errors)


@pytest.mark.parametrize("panel", PANELS)
def test_panel_state_is_stable_through_set_state(report, panel):
    """set_state(get_state()) must be a no-op; anything else means a key is
    produced but not restored, which is silently lost on reload."""
    stable = report[panel].get("roundtrip_stable")
    if stable is None:
        pytest.skip(f"{panel} has no state")
    assert stable is True


def test_panels_expose_their_parameters(report):
    """get_params() returns either a dict of settings or a params dataclass.

    ReconstructionPanel hands back a ColmapParams rather than a mapping, which
    is deliberate — it is what the engine consumes.
    """
    exposed = {k: v.get("get_params") for k, v in report.items() if "get_params" in v}
    assert exposed, "no panel exposed get_params"
    for name, params in exposed.items():
        assert isinstance(params, list) or params.endswith("Params"), \
            f"{name}: get_params returned {params}"
