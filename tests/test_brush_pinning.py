"""Épinglage de la release Brush : la version et son empreinte ne doivent jamais diverger.

Contexte (2026-08-07) : l'installeur résolvait la *dernière* release amont via
`get_remote_version()` tout en vérifiant l'archive contre une empreinte figée
dans `checksums.json`. Les deux étaient donc condamnés à diverger au premier tag
publié en amont — l'installation de Brush était refusée par la garde fail-closed
`verify_download_strict()`, et `base.py` proposait en boucle une mise à jour vers
un échec certain. La version est désormais épinglée à côté de son empreinte.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.scripts.checksum_verifier import CHECKSUMS_PATH, load_expected_checksums
from app.scripts.installers.brush import BrushEngineDep


# ── Cohérence du fichier d'épinglage (aurait attrapé la dérive d'origine) ─────
def test_pinned_release_and_hash_are_both_present():
    """Bumper l'un sans l'autre remet exactement la panne d'origine en place."""
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


# ── get_remote_version : la version épinglée, pas « latest » ──────────────────
@pytest.fixture
def installer(tmp_path):
    inst = BrushEngineDep()
    inst.root = tmp_path  # pas de config.json → build_mode "release" par défaut
    return inst


def test_release_mode_returns_the_pinned_version_not_latest(installer):
    """Le cœur du correctif : même si l'amont a publié plus récent, on installe
    ce que l'on sait vérifier."""
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
    """Sans réseau, l'installation reste possible : le tag amont n'est
    qu'informatif, il ne conditionne rien."""
    with patch.object(BrushEngineDep, "_fetch_latest_release_tag", return_value=""):
        assert installer.get_remote_version() == load_expected_checksums()["brush_release"]


def test_missing_pin_returns_empty_rather_than_guessing(installer):
    """Sans épinglage, on ne devine pas une version : l'appelant annule."""
    with patch("app.scripts.installers.brush.load_expected_checksums", return_value={}), \
         patch.object(BrushEngineDep, "_fetch_latest_release_tag", return_value="v9.9.9"):
        assert installer.get_remote_version() == ""


def test_source_mode_ignores_the_pin(installer):
    """Le mode source suit HEAD : l'épinglage ne concerne que les binaires
    téléchargés, qui sont les seuls à être vérifiés par empreinte."""
    (installer.root / "config.json").write_text(
        json.dumps({"brush_params": {"build_mode": "source"}})
    )
    with patch.object(BrushEngineDep, "_get_head_commit", return_value="abc123def456"):
        assert installer.get_remote_version() == "abc123def456"
