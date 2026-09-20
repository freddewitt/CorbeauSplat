"""Pinning of the Brush release: the version and its fingerprint must never diverge.

Context (2026-08-07): the installer resolved the *latest* upstream release
through `get_remote_version()` while checking the archive against a fingerprint
frozen in `checksums.json`. Both were therefore doomed to diverge on the first
tag published upstream — the Brush installation was refused by the fail-closed
`verify_download_strict()` guard, and `base.py` kept offering an update towards
a certain failure. The version is now pinned next to its fingerprint.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.scripts.checksum_verifier import CHECKSUMS_PATH, load_expected_checksums
from app.scripts.installers.brush import BrushEngineDep


# ── Consistency of the pinning file (would have caught the original drift) ────
def test_pinned_release_and_hash_are_both_present():
    """Bumping one without the other puts the original breakage right back."""
    checksums = json.loads(Path(CHECKSUMS_PATH).read_text())
    assert checksums.get("brush_release"), "brush_release manquant de checksums.json"
    assert checksums.get("darwin_brush"), "darwin_brush manquant de checksums.json"


def test_pinned_release_looks_like_a_tag():
    checksums = json.loads(Path(CHECKSUMS_PATH).read_text())
    assert checksums["brush_release"].startswith("v")


def test_pinned_hash_is_a_sha256():
    checksums = json.loads(Path(CHECKSUMS_PATH).read_text())
    digest = checksums["darwin_brush"]
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


# ── get_remote_version: the pinned version, not "latest" ──────────────────────
@pytest.fixture
def installer(tmp_path):
    inst = BrushEngineDep()
    inst.root = tmp_path  # no config.json → build_mode "release" by default
    return inst


def test_release_mode_returns_the_pinned_version_not_latest(installer):
    """The heart of the fix: even when upstream published something newer, we
    install what we know how to verify."""
    with patch.object(BrushEngineDep, "_fetch_latest_release_tag", return_value="v9.9.9"):
        assert installer.get_remote_version() == load_expected_checksums()["brush_release"]


def test_upstream_ahead_is_only_a_notice(installer, capsys):
    with patch.object(BrushEngineDep, "_fetch_latest_release_tag", return_value="v9.9.9"):
        installer.get_remote_version()
    out = capsys.readouterr().out
    assert "v9.9.9" in out
    assert "checksums.json" in out


def test_no_notice_when_upstream_matches_the_pin(installer, capsys):
    pinned = load_expected_checksums()["brush_release"]
    with patch.object(BrushEngineDep, "_fetch_latest_release_tag", return_value=pinned):
        installer.get_remote_version()
    assert "disponible en amont" not in capsys.readouterr().out


def test_offline_still_returns_the_pin(installer):
    """Without a network, installing stays possible: the upstream tag is only
    informative, it conditions nothing."""
    with patch.object(BrushEngineDep, "_fetch_latest_release_tag", return_value=""):
        assert installer.get_remote_version() == load_expected_checksums()["brush_release"]


def test_missing_pin_returns_empty_rather_than_guessing(installer):
    """Without a pin we do not guess a version: the caller cancels."""
    with patch("app.scripts.installers.brush.load_expected_checksums", return_value={}), \
         patch.object(BrushEngineDep, "_fetch_latest_release_tag", return_value="v9.9.9"):
        assert installer.get_remote_version() == ""


def test_source_mode_ignores_the_pin(installer):
    """Source mode follows HEAD: the pinning only concerns downloaded
    binaries, the only ones checked against a fingerprint."""
    (installer.root / "config.json").write_text(
        json.dumps({"brush_params": {"build_mode": "source"}})
    )
    with patch.object(BrushEngineDep, "_get_head_commit", return_value="abc123def456"):
        assert installer.get_remote_version() == "abc123def456"
