"""Tests de la surface structurée BrushParams + non-régression des tokens.

Garantie critique : passer ``BrushParams.to_engine_params()`` à
``BrushEngine.build_command()`` doit produire exactement les mêmes tokens que
l'appel direct avec le dict équivalent (l'allowlist du moteur reste seule juge).
"""

import pytest

from app.core.brush_engine import BrushEngine
from app.core.brush_params import BrushParams

# Presets intégrés (dupliqués ici en constante de test pour ne pas dépendre de
# la couche CLI ; miroir de BRUSH_PRESETS de app/cli/commands.py).
BUILTIN_PRESETS = {
    "fast": {
        "total_steps": 7000, "refine_every": 100,
        "growth_grad_threshold": 0.01, "growth_select_fraction": 0.2,
        "growth_stop_iter": 6000,
    },
    "std": {
        "total_steps": 30000, "refine_every": 200,
        "growth_grad_threshold": 0.003, "growth_select_fraction": 0.2,
        "growth_stop_iter": 15000,
    },
    "dense": {
        "total_steps": 50000, "refine_every": 100,
        "growth_grad_threshold": 0.0005, "growth_select_fraction": 0.6,
        "growth_stop_iter": 40000,
    },
}


@pytest.fixture
def engine():
    eng = BrushEngine()
    eng.brush_bin = "/fake/brush"  # déterministe, indépendant de l'install réelle
    return eng


def _cmd(engine, params):
    cmd, _env = engine.build_command("/in", "/out", params)
    return cmd


# ── Sérialisation ────────────────────────────────────────────────────────────
def test_to_dict_from_dict_roundtrip():
    p = BrushParams(total_steps=30000, sh_degree=3, max_splats=2_000_000, device="mps")
    restored = BrushParams.from_dict(p.to_dict())
    assert restored == p


def test_from_dict_ignores_unknown_keys():
    p = BrushParams.from_dict({"total_steps": 7000, "obsolete_key": "x"})
    assert p.total_steps == 7000


def test_from_dict_non_dict_returns_defaults():
    assert BrushParams.from_dict(None) == BrushParams()


# ── to_engine_params ─────────────────────────────────────────────────────────
def test_none_fields_omitted():
    params = BrushParams().to_engine_params()
    assert "max_splats" not in params
    assert "total_steps" not in params
    # checkpoint_interval a un défaut explicite (reproduit build_command)
    assert params["checkpoint_interval"] == 7000


def test_native_fields_passthrough():
    params = BrushParams(total_steps=30000, max_splats=1_000_000, sh_degree=2).to_engine_params()
    assert params["total_steps"] == 30000
    assert params["max_splats"] == 1_000_000
    assert params["sh_degree"] == 2


def test_promoted_flags_folded_into_custom_args():
    params = BrushParams(
        save_iterations="5000", eval_every="1000", refine_pose="true",
    ).to_engine_params()
    ca = params["custom_args"]
    assert "--save-iterations 5000" in ca
    assert "--eval-every 1000" in ca
    assert "--refine-pose true" in ca


def test_promoted_flags_appended_after_user_custom_args():
    params = BrushParams(custom_args="--log-level debug", save_iterations="5000").to_engine_params()
    assert params["custom_args"] == "--log-level debug --save-iterations 5000"


def test_promoted_flags_survive_allowlist_in_build_command(engine):
    params = BrushParams(save_iterations="5000", eval_every="1000").to_engine_params()
    cmd = _cmd(engine, params)
    assert "--save-iterations" in cmd and "5000" in cmd
    assert "--eval-every" in cmd and "1000" in cmd


# ── Non-régression stricte des tokens ────────────────────────────────────────
@pytest.mark.parametrize("preset_name", ["fast", "std", "dense"])
def test_tokens_identical_to_direct_dict_for_presets(engine, preset_name):
    preset = BUILTIN_PRESETS[preset_name]
    via_dict = _cmd(engine, preset)
    via_params = _cmd(engine, BrushParams.from_dict(preset).to_engine_params())
    assert via_params == via_dict


def test_empty_params_still_emit_default_export_every(engine):
    """build_command émet toujours --export-every 7000 par défaut ; BrushParams
    doit reproduire ce comportement."""
    cmd = _cmd(engine, BrushParams().to_engine_params())
    assert "--export-every" in cmd
    idx = cmd.index("--export-every")
    assert cmd[idx + 1] == "7000"
