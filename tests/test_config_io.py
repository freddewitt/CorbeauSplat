"""Tests de la sauvegarde/chargement de configurations nommées (config_io.py)."""

import pytest

from app.core import config_io
from app.core.config_io import (
    CONFIG_VERSION,
    ChainConfig,
    delete_config,
    is_safe_config_name,
    list_configs,
    load_config,
    save_config,
)


@pytest.fixture(autouse=True)
def tmp_root(tmp_path, monkeypatch):
    """Redirige le stockage des configs vers un dossier temporaire."""
    monkeypatch.setattr(config_io, "resolve_project_root", lambda: tmp_path)
    return tmp_path


# ── Sanitisation des noms ────────────────────────────────────────────────────
@pytest.mark.parametrize("bad", ["", "   ", "..", "a/b", "a\\b", "../evil"])
def test_unsafe_names_rejected(bad):
    assert not is_safe_config_name(bad)


@pytest.mark.parametrize("good", ["mon-projet", "config_1", "Scene 42"])
def test_safe_names_accepted(good):
    assert is_safe_config_name(good)


def test_save_load_rejects_unsafe_name():
    with pytest.raises(ValueError):
        save_config("../evil", ChainConfig())
    with pytest.raises(ValueError):
        load_config("a/b")
    with pytest.raises(ValueError):
        delete_config("..")


# ── Round-trip ───────────────────────────────────────────────────────────────
def test_save_and_load_roundtrip():
    cfg = ChainConfig(
        source={"input_path": "/data/video.mp4", "output_path": "/out"},
        colmap={"camera_model": "PINHOLE", "max_image_size": 2000},
        brush={"total_steps": 30000},
        flags={"entrainement_apres": True},
    )
    save_config("scene1", cfg)
    loaded = load_config("scene1")
    assert loaded.source["input_path"] == "/data/video.mp4"
    assert loaded.colmap["camera_model"] == "PINHOLE"
    assert loaded.brush["total_steps"] == 30000
    assert loaded.flags["entrainement_apres"] is True
    assert loaded.version == CONFIG_VERSION


def test_save_accepts_plain_dict():
    save_config("raw", {"source": {"x": 1}})
    loaded = load_config("raw")
    assert loaded.source == {"x": 1}


def test_list_and_delete():
    save_config("a", ChainConfig())
    save_config("b", ChainConfig())
    assert list_configs() == ["a", "b"]
    assert delete_config("a") is True
    assert list_configs() == ["b"]
    assert delete_config("absent") is False


def test_load_missing_raises():
    with pytest.raises(FileNotFoundError):
        load_config("nexiste_pas")


# ── Tolérance aux sections manquantes / versions anciennes ───────────────────
def test_from_dict_tolerates_missing_sections():
    cfg = ChainConfig.from_dict({"source": {"input_path": "/x"}})
    assert cfg.source == {"input_path": "/x"}
    assert cfg.colmap == {}
    assert cfg.flags == {}


def test_from_dict_ignores_unknown_sections():
    cfg = ChainConfig.from_dict({"source": {}, "section_future": {"y": 1}})
    assert not hasattr(cfg, "section_future")


def test_typed_helpers_reload_objects():
    cfg = ChainConfig(
        colmap={"camera_model": "PINHOLE"},
        flags={"visualiser_apres": True},
    )
    params = cfg.colmap_params()
    assert params.camera_model == "PINHOLE"
    state = cfg.run_state()
    assert state.visualiser_apres is True


def test_old_config_missing_keys_reloads_with_defaults():
    """Une config d'une version antérieure (colmap partiel) se recharge sans casser."""
    save_config("old", {"version": 0, "colmap": {"camera_model": "RADIAL"}})
    cfg = load_config("old")
    params = cfg.colmap_params()
    assert params.camera_model == "RADIAL"
    # champ absent → défaut de ColmapParams
    assert params.max_image_size == 3200
