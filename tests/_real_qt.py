"""Run a snippet against a real PySide6, in a subprocess, with coverage.

The suite installs a session-wide PySide6 mock (tests/conftest.py) that is
process-global and cannot be undone mid-run, so a genuine panel can only be
built in a fresh interpreter. Coverage does not follow a subprocess on its own,
which is why the panels read as 9-14% covered while being exercised: the
bootstrap below starts a coverage session inside the child when the parent is
measuring, and the parent's `combine` step picks up the data file.
"""
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_COVERAGE_BOOTSTRAP = """
import os as _os
if _os.environ.get("COVERAGE_PROCESS_START"):
    try:
        import coverage as _coverage
        _cov = _coverage.Coverage(source=["app"], data_suffix=True, auto_data=True)
        _cov.start()
        import atexit as _atexit

        def _stop():
            _cov.stop()
            _cov.save()

        _atexit.register(_stop)
    except Exception:
        pass
"""


def run(script: str, timeout: int = 300) -> subprocess.CompletedProcess:
    """Execute `script` in a fresh interpreter with real Qt, offscreen."""
    env = {
        "QT_QPA_PLATFORM": "offscreen",
        # The real PATH: ffprobe and ffmpeg live outside /usr/bin on Homebrew.
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(Path.home()),
        "PYTHONPATH": str(PROJECT_ROOT),
    }
    if os.environ.get("COVERAGE_RUN") or os.environ.get("COVERAGE_PROCESS_START"):
        env["COVERAGE_PROCESS_START"] = os.environ.get(
            "COVERAGE_PROCESS_START", str(PROJECT_ROOT / "pyproject.toml")
        )
    return subprocess.run(
        [sys.executable, "-c", _COVERAGE_BOOTSTRAP + script],
        capture_output=True, text=True, timeout=timeout,
        cwd=str(PROJECT_ROOT), env=env,
    )


def run_for_payload(script: str, marker: str = "REPORT=", timeout: int = 300):
    """Run `script` and return the JSON payload it printed after `marker`."""
    import json

    import pytest

    proc = run(script, timeout=timeout)
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith(marker)), None)
    if line is None:
        if "No module named 'PySide6'" in proc.stderr:
            pytest.skip("real PySide6 not importable in this environment")
        pytest.fail(f"real-Qt subprocess produced no payload:\n{proc.stderr[-3000:]}")
    return json.loads(line[len(marker):])
