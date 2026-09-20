"""Pinning of the pip engines (Sharp, Extractor 360, 4DGS/nerfstudio).

Context (audit F-002): the three engines install a **pinned** ref through
`update_git()` (a commit SHA or a tag), yet persisted `get_remote_version()`
— the SHA of the *moving* default-branch HEAD resolved with `git ls-remote` —
as their local version. On every commit pushed upstream, that recorded value
differed from the freshly resolved HEAD, so `base.main_install` offered/re-ran
a full `pip install` of code that had not changed. The recorded local version
must be the pinned ref, so the comparison is stable between pin bumps.
"""

import json
from contextlib import ExitStack
from unittest.mock import patch

import pytest

from app.scripts.installers.base import DependencyManager
from app.scripts.installers.extractor_360 import EXTRACTOR_360_PINNED_TAG, Extractor360EngineDep
from app.scripts.installers.four_dgs import NERFSTUDIO_PINNED_TAG, FourDGSEngineDep
from app.scripts.installers.sharp import SHARP_PINNED_REF, SharpEngineDep

OLD_HEAD = "cafecafecafecafecafecafecafecafecafecafe"  # head recorded before the fix
NEW_HEAD = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"  # a later upstream push

PIP_ENGINES = [
    (SharpEngineDep, SHARP_PINNED_REF),
    (Extractor360EngineDep, EXTRACTOR_360_PINNED_TAG),
    (FourDGSEngineDep, NERFSTUDIO_PINNED_TAG),
]


def _make_dep(tmp_path, engine_cls):
    """Instantiate an engine whose filesystem paths live under tmp_path."""
    with patch("app.scripts.installers.base.resolve_project_root", return_value=tmp_path):
        return engine_cls()


def _mark_installed(dep):
    """Simulate an existing install: the venv marker binary is present."""
    dep.python_bin.parent.mkdir(parents=True)
    dep.python_bin.write_text("python")


def _install_heavy_steps(dep):
    """Patchers for the network/build steps of install(): only the version
    bookkeeping runs. Sharp additionally needs a python3.11 on PATH."""
    patchers = [
        patch.object(dep, "update_git"),
        patch.object(dep, "create_venv"),
        patch.object(dep, "pip_install"),
    ]
    if isinstance(dep, SharpEngineDep):
        patchers.append(patch("app.scripts.installers.sharp.shutil.which", return_value="/usr/bin/python3.11"))
    return patchers


def _patched_install(dep, *extras):
    """ExitStack patching install()'s heavy steps plus any extras."""
    stack = ExitStack()
    for p in _install_heavy_steps(dep) + list(extras):
        stack.enter_context(p)
    return stack


def _enabled_manager(tmp_path, dep, name="extractor_360"):
    """A DependencyManager whose engines_dir matches dep's layout, so
    get_config() reads tmp_path/config.json (as in the real app)."""
    manager = DependencyManager(tmp_path / "engines")
    manager.engines = {name: dep}
    (tmp_path / "config.json").write_text(json.dumps({f"{name}_enabled": True}))
    return manager


# ── get_remote_version: the pinned ref, not the moving default-branch HEAD ──
@pytest.mark.parametrize("engine_cls, pinned", PIP_ENGINES)
def test_get_remote_version_reports_the_pin_not_the_moving_head(tmp_path, engine_cls, pinned):
    """An upstream push since install must not change the target version."""
    dep = _make_dep(tmp_path, engine_cls)
    with patch("subprocess.check_output", return_value=f"{NEW_HEAD}\tHEAD\n"):
        assert dep.get_remote_version() == pinned


# ── install(): the recorded local version is the pinned ref ──────────────────
@pytest.mark.parametrize("engine_cls, pinned", PIP_ENGINES)
def test_install_records_the_pinned_ref(tmp_path, engine_cls, pinned):
    """save_local_version() receives the pin, so the comparison
    remote != local in main_install does not fire on every push."""
    dep = _make_dep(tmp_path, engine_cls)
    with _patched_install(dep), \
         patch("subprocess.check_output", return_value=f"{NEW_HEAD}\tHEAD\n"):
        dep.install()
    assert dep.get_local_version() == pinned


# ── main_install: no reinstall loop when the pinned ref is already installed ─
def test_no_reinstall_loop_on_upstream_push(tmp_path):
    """Once installed at the pinned ref, a new commit pushed upstream must not
    trigger a full reinstall."""
    dep = _make_dep(tmp_path, Extractor360EngineDep)
    _mark_installed(dep)
    dep.save_local_version(EXTRACTOR_360_PINNED_TAG)

    manager = _enabled_manager(tmp_path, dep)

    with patch("app.scripts.installers.tools.install_system_dependencies"), \
         patch.object(dep, "install") as mock_install, \
         patch("subprocess.check_output", return_value=f"{NEW_HEAD}\tHEAD\n"):
        manager.main_install()

    mock_install.assert_not_called()


# ── migration: a legacy recorded HEAD SHA is re-written to the pin once ──────
def test_legacy_moving_head_local_version_is_migrated_in_one_install(tmp_path):
    """An engine installed before the fix recorded a HEAD SHA (OLD_HEAD) as its
    local version. After the fix the next run must reinstall exactly once and
    record the pin — the pre-fix behaviour recorded the fresh NEW_HEAD instead,
    which is never the pin and keeps the install churning on every push."""
    dep = _make_dep(tmp_path, Extractor360EngineDep)
    _mark_installed(dep)
    dep.save_local_version(OLD_HEAD)  # legacy: what the buggy code had recorded

    manager = _enabled_manager(tmp_path, dep)

    with patch("app.scripts.installers.tools.install_system_dependencies"), \
         patch("subprocess.check_output", return_value=f"{NEW_HEAD}\tHEAD\n"), \
         _patched_install(dep):
        manager.main_install()

    assert dep.get_local_version() == EXTRACTOR_360_PINNED_TAG


# ── legitimate behaviour: a deliberate pin bump still surfaces as an update ──
def test_pin_bump_still_triggers_an_update(tmp_path):
    """Bumping the pinned tag must keep offering the update: the fix silences
    upstream noise, not deliberate version changes."""
    dep = _make_dep(tmp_path, Extractor360EngineDep)
    _mark_installed(dep)
    dep.save_local_version("v4.0.0")  # previous pin

    manager = _enabled_manager(tmp_path, dep)

    with patch("app.scripts.installers.tools.install_system_dependencies"), \
         patch.object(dep, "install") as mock_install, \
         patch("app.scripts.installers.extractor_360.EXTRACTOR_360_PINNED_TAG", "v4.1.0"), \
         patch("subprocess.check_output", return_value=f"{NEW_HEAD}\tHEAD\n"):
        manager.main_install()

    mock_install.assert_called_once()
