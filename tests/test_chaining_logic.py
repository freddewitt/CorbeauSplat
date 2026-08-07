"""Câblage des champs du panneau Projet vers les étapes chaînées.

`checkpoint_dest`, `export_dir` et `export_format` étaient saisissables et
sérialisés (`SourcePanel.get_state`/`set_state`) mais aucun worker ne les lisait
— l'utilisateur pouvait les remplir sans le moindre effet. La logique vit dans
`chaining_logic.py`, hors Qt, pour être testable sans `StudioWindow` (dont la
classe de base Qt est un MagicMock sous le conftest).
"""

from pathlib import Path

from app.gui.chaining_logic import (
    keeps_only_latest_checkpoint,
    resolve_checkpoints_dir,
    resolve_export_dir,
    resolve_export_format,
)


def _source_state(**overrides):
    state = {
        "project_name": "MonProjet",
        "output_path": "/out",
        "checkpoint_dest": "",
        "export_dir": "",
        "export_format": "",
    }
    state.update(overrides)
    return state


# ── checkpoint_dest ──────────────────────────────────────────────────────────
def test_checkpoints_dir_default_is_project_subfolder():
    assert resolve_checkpoints_dir(_source_state()) == Path("/out/MonProjet/checkpoints")


def test_checkpoints_dir_custom_dest_keeps_1_2_3_semantics():
    """Sémantique d'origine (CHANGELOG 1.2.3) : `<destination>/<projet>`, sans
    sous-dossier `checkpoints`."""
    state = _source_state(checkpoint_dest="/ailleurs/ckpt")
    assert resolve_checkpoints_dir(state) == Path("/ailleurs/ckpt/MonProjet")


def test_checkpoints_dir_custom_dest_is_resolved():
    """La destination est une entrée utilisateur libre : elle passe par
    `validate_path_standalone`, donc elle ressort résolue."""
    state = _source_state(checkpoint_dest="/ailleurs/./ckpt/../ckpt")
    assert resolve_checkpoints_dir(state) == Path("/ailleurs/ckpt/MonProjet")


def test_checkpoints_dir_without_output_path():
    assert resolve_checkpoints_dir(_source_state(output_path="")) is None


def test_checkpoints_dir_falls_back_to_untitled():
    assert resolve_checkpoints_dir(_source_state(project_name="   ")) == Path(
        "/out/Untitled/checkpoints"
    )


def test_checkpoints_dir_tolerates_missing_key():
    """Les configs enregistrées avant l'ajout du champ n'ont pas la clé."""
    state = _source_state()
    del state["checkpoint_dest"]
    assert resolve_checkpoints_dir(state) == Path("/out/MonProjet/checkpoints")


def test_keep_only_latest_follows_the_field():
    assert keeps_only_latest_checkpoint(_source_state()) is False
    assert keeps_only_latest_checkpoint(_source_state(checkpoint_dest="  ")) is False
    assert keeps_only_latest_checkpoint(_source_state(checkpoint_dest="/x")) is True


# ── export_dir ───────────────────────────────────────────────────────────────
_PLY = "/out/MonProjet/checkpoints/final.ply"


def test_export_dir_overrides_panel_output():
    state = _source_state(export_dir="/exports")
    assert resolve_export_dir(state, _PLY, "/saisi/a/la/main") == "/exports"


def test_export_dir_empty_falls_back_to_ply_parent():
    assert resolve_export_dir(_source_state(), _PLY, "") == "/out/MonProjet/checkpoints"


def test_export_dir_empty_does_not_clobber_manual_output():
    assert resolve_export_dir(_source_state(), _PLY, "/saisi/a/la/main") is None


def test_export_dir_is_resolved():
    state = _source_state(export_dir="/exports/./sous/..")
    assert resolve_export_dir(state, _PLY, "") == "/exports"


# ── export_format ────────────────────────────────────────────────────────────
def test_export_format_passthrough():
    assert resolve_export_format(_source_state(export_format="obj")) == "obj"


def test_export_format_empty_leaves_panel_in_charge():
    assert resolve_export_format(_source_state()) == ""
    assert resolve_export_format(_source_state(export_format=None)) == ""


def test_export_format_values_match_the_export_engine():
    """Le combo du panneau Projet et celui du panneau Export doivent proposer
    les mêmes formats, sinon `findData` échouerait silencieusement et le réglage
    serait ignoré. Les deux lisent désormais `ExportEngine.SUPPORTED_FORMATS`."""
    from app.core.export_engine import ExportEngine

    for fmt in ExportEngine.SUPPORTED_FORMATS:
        assert resolve_export_format(_source_state(export_format=fmt)) == fmt
