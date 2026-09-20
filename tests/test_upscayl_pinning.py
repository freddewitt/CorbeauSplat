"""Pinning of the upscayl-ncnn release: the tag and its fingerprint must never diverge.

Context: the installer resolved the *latest* upstream release through
`get_remote_version()` while verifying the archive against a fingerprint frozen
in `checksums.json` for a specific tag (``upscayl_release``). Both were doomed
to diverge on the first tag published upstream — `base.py` would offer an update
towards a release whose fingerprint does not exist, `verify_download_strict()`
would refuse it, and the whole installer would abort. The tag is now pinned next
to its fingerprint, exactly like Brush (`brush_release`): a new release is
adopted only by a deliberate, reviewed bump of `checksums.json`.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.scripts.checksum_verifier import CHECKSUMS_PATH
from app.scripts.installers.upscayl import UpscaylEngineDep

PINNED_TAG = "20251207-174704"
NEWER_TAG = "99999999-000000"


# ── Consistency of the pinning file (would have caught the original drift) ────
def test_pinned_release_and_hash_are_both_present():
    """Bumping one without the other puts the original breakage right back."""
    checksums = json.loads(Path(CHECKSUMS_PATH).read_text())
    assert checksums.get("upscayl_release"), "upscayl_release manquant de checksums.json"
    assert checksums.get("darwin_upscayl"), "darwin_upscayl manquant de checksums.json"


def test_pinned_release_is_the_documented_tag():
    """The pin in checksums.json matches the documented tag the hashes were
    computed from."""
    checksums = json.loads(Path(CHECKSUMS_PATH).read_text())
    assert checksums["upscayl_release"] == PINNED_TAG


def test_pinned_hash_is_a_sha256():
    checksums = json.loads(Path(CHECKSUMS_PATH).read_text())
    digest = checksums["darwin_upscayl"]
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


# ── get_remote_version: the pinned version, not "latest" ──────────────────────
@pytest.fixture
def installer():
    return UpscaylEngineDep()


class _FakeApiResp:
    """Minimal stand-in for a `urllib.request.urlopen` response."""

    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return json.dumps(self._payload).encode()


def test_returns_pinned_version_not_latest(installer):
    """The heart of the fix: even when upstream published something newer, we
    report (and later install) only what we know how to verify."""
    with patch("urllib.request.urlopen", return_value=_FakeApiResp({"tag_name": NEWER_TAG})):
        assert installer.get_remote_version() == PINNED_TAG


def test_upstream_ahead_is_only_a_notice(installer, capsys):
    """A newer upstream tag is a heads-up pointing at checksums.json, never a
    trigger for an unverified install."""
    with patch("urllib.request.urlopen", return_value=_FakeApiResp({"tag_name": NEWER_TAG})):
        installer.get_remote_version()
    out = capsys.readouterr().out
    assert NEWER_TAG in out
    assert "checksums.json" in out


def test_no_notice_when_upstream_matches_the_pin(installer, capsys):
    with patch("urllib.request.urlopen", return_value=_FakeApiResp({"tag_name": PINNED_TAG})):
        installer.get_remote_version()
    assert "disponible en amont" not in capsys.readouterr().out


def test_offline_still_returns_the_pin(installer):
    """Without a network, installing stays possible: the upstream tag is only
    informative, it conditions nothing."""
    with patch("urllib.request.urlopen", side_effect=OSError("no network")):
        assert installer.get_remote_version() == PINNED_TAG


def test_missing_pin_returns_empty_rather_than_guessing(tmp_path):
    """Without a pin we do not guess a version: the caller cancels."""
    empty = tmp_path / "empty.json"
    empty.write_text("{}")
    with patch("app.scripts.checksum_verifier.CHECKSUMS_PATH", empty), \
         patch("urllib.request.urlopen", return_value=_FakeApiResp({"tag_name": NEWER_TAG})):
        assert UpscaylEngineDep().get_remote_version() == ""


# ── main_install: an unverified "latest" must never trigger an install ────────
def test_main_install_does_not_trigger_update_for_unverified_latest(tmp_path, capsys):
    """A newer upstream tag must not reach `engine.install()`: remote stays the
    pinned tag, so base.py's `remote != local` never fires for an unverified
    release."""
    from app.scripts.installers.base import DependencyManager

    dep = UpscaylEngineDep()
    dep.root = tmp_path
    dep.engines_dir = tmp_path / "engines"
    (tmp_path / "engines").mkdir(parents=True, exist_ok=True)
    dep.version_file = dep.engines_dir / "upscayl.version"
    dep.version_file.write_text(PINNED_TAG)

    manager = DependencyManager(tmp_path)
    manager.engines = {"upscayl": dep}

    with patch("app.scripts.installers.tools.install_system_dependencies"), \
         patch.object(UpscaylEngineDep, "is_installed", return_value=True), \
         patch.object(UpscaylEngineDep, "_fetch_latest_release_tag", return_value=NEWER_TAG), \
         patch.object(UpscaylEngineDep, "install") as mock_install, \
         patch("urllib.request.urlopen", return_value=_FakeApiResp({"tag_name": NEWER_TAG})):
        manager.main_install()

    out = capsys.readouterr().out
    assert "disponible en amont" in out
    mock_install.assert_not_called()
