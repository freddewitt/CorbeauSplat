"""Tests de la logique de navigation du Studio (studio_nav.py).

Logique pure (hors Qt), donc exécutable sous le mock PySide6 de la CI. Couvre le
câblage rail→page (sélection change la page) et le repli/dépli des sections. Le
rendu Qt lui-même est validé manuellement sur Apple Silicon (vérifs Lot 2).
"""

from app.core.run_state import PIPELINE_STEPS
from app.gui.rail import TOOL_KEYS
from app.gui.studio_nav import CollapseState, PageRegistry

_ALL_KEYS = tuple(PIPELINE_STEPS) + tuple(TOOL_KEYS)


# ── PageRegistry ─────────────────────────────────────────────────────────────
def test_registry_maps_all_keys_to_unique_indices():
    reg = PageRegistry(_ALL_KEYS)
    assert set(reg.keys()) == set(_ALL_KEYS)
    assert sorted(reg.as_dict().values()) == list(range(len(_ALL_KEYS)))


def test_registry_initial_current_is_first_key():
    reg = PageRegistry(_ALL_KEYS)
    assert reg.current == _ALL_KEYS[0] == "source"


def test_registry_select_changes_current_and_returns_index():
    reg = PageRegistry(_ALL_KEYS)
    idx = reg.select("export")
    assert reg.current == "export"
    assert idx == reg.index_of("export")


def test_registry_select_every_key():
    reg = PageRegistry(_ALL_KEYS)
    for key in _ALL_KEYS:
        assert reg.select(key) == reg.index_of(key)
        assert reg.current == key


def test_registry_unknown_key_is_noop():
    reg = PageRegistry(_ALL_KEYS)
    reg.select("export")
    assert reg.select("inconnu") is None
    assert reg.current == "export"  # inchangé


def test_registry_empty():
    reg = PageRegistry([])
    assert reg.current is None
    assert reg.index_of("x") is None
    assert reg.select("x") is None


# ── CollapseState ────────────────────────────────────────────────────────────
def test_collapse_default_collapsed():
    assert CollapseState().collapsed is True


def test_collapse_set_and_toggle():
    st = CollapseState()
    assert st.set(False) is False
    assert st.collapsed is False
    assert st.toggle() is True
    assert st.toggle() is False


def test_collapse_can_start_expanded():
    assert CollapseState(collapsed=False).collapsed is False
