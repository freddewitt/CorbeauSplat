"""Tests des presets Brush personnalisés (brush_presets.py)."""

import pytest

from app.core import brush_presets
from app.core.brush_presets import (
    delete_user_preset,
    is_deletable,
    load_user_presets,
    merge_presets,
    save_user_preset,
)

BUILTINS = {"fast": {"total_steps": 7000}, "std": {"total_steps": 30000}}


@pytest.fixture(autouse=True)
def tmp_root(tmp_path, monkeypatch):
    monkeypatch.setattr(brush_presets, "resolve_project_root", lambda: tmp_path)
    return tmp_path


def test_no_presets_initially():
    assert load_user_presets() == {}


def test_save_and_load_user_preset():
    save_user_preset("mon-preset", {"total_steps": 12345, "max_splats": 500000})
    presets = load_user_presets()
    assert presets["mon-preset"]["total_steps"] == 12345


def test_save_rejects_unsafe_name():
    with pytest.raises(ValueError):
        save_user_preset("../evil", {"total_steps": 1})


def test_overwrite_existing_preset():
    save_user_preset("p", {"total_steps": 1})
    save_user_preset("p", {"total_steps": 2})
    assert load_user_presets()["p"]["total_steps"] == 2


def test_delete_user_preset():
    save_user_preset("p", {"total_steps": 1})
    assert delete_user_preset("p") is True
    assert delete_user_preset("p") is False
    assert load_user_presets() == {}


def test_merge_builtins_and_user():
    save_user_preset("custom", {"total_steps": 99})
    merged = merge_presets(BUILTINS)
    assert set(merged) == {"fast", "std", "custom"}
    assert merged["custom"]["total_steps"] == 99


def test_user_preset_overrides_builtin_on_name_collision():
    save_user_preset("fast", {"total_steps": 111})
    merged = merge_presets(BUILTINS)
    assert merged["fast"]["total_steps"] == 111


def test_merge_with_no_builtins():
    save_user_preset("only", {"total_steps": 5})
    assert merge_presets({}) == {"only": {"total_steps": 5}}


def test_corrupt_store_returns_empty(tmp_root):
    (tmp_root / "brush_presets.json").write_text("{ this is not json", encoding="utf-8")
    assert load_user_presets() == {}


# ── Garde-fou de suppression (bouton 🗑 d'EntrainementPanel) ──────────────────
def test_builtin_preset_is_not_deletable():
    """Un preset intégré ne doit pas être supprimable : le retirer du dropdown
    n'aurait aucun effet persistant, `merge_presets` le réinjecterait."""
    assert is_deletable("fast") is False


def test_default_entry_is_not_deletable():
    """L'entrée « Défaut » du dropdown porte `None` comme data."""
    assert is_deletable(None) is False
    assert is_deletable("") is False


def test_user_preset_is_deletable():
    save_user_preset("mon-preset", {"total_steps": 1})
    assert is_deletable("mon-preset") is True


def test_user_preset_shadowing_a_builtin_is_deletable_and_restores_it():
    """Supprimer un preset utilisateur homonyme d'un intégré fait réapparaître
    l'intégré — comportement attendu de `merge_presets`."""
    save_user_preset("fast", {"total_steps": 999})
    assert is_deletable("fast") is True
    assert merge_presets(BUILTINS)["fast"]["total_steps"] == 999

    assert delete_user_preset("fast") is True
    assert is_deletable("fast") is False
    assert merge_presets(BUILTINS)["fast"]["total_steps"] == 7000
