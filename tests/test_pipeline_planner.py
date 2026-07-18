"""Tests du chaînage conditionnel du run (pipeline_planner.py)."""

from app.core.run_state import RunState
from app.gui.pipeline_planner import plan_pipeline


def _rs(**flags):
    rs = RunState()
    for k, v in flags.items():
        rs.set_flag(k, v)
    return rs


def test_gsplat_minimal():
    assert plan_pipeline("gsplat", _rs()) == ["source", "reconstruction"]


def test_gsplat_with_training():
    plan = plan_pipeline("gsplat", _rs(entrainement_apres=True))
    assert plan == ["source", "reconstruction", "entrainement"]


def test_gsplat_full_chain():
    rs = _rs(entrainement_apres=True, nettoyer_apres=True,
             exporter_apres=True, visualiser_apres=True)
    assert plan_pipeline("gsplat", rs) == [
        "source", "reconstruction", "entrainement", "nettoyage", "export", "visualiser",
    ]


def test_sharp_has_no_training_step():
    rs = _rs(entrainement_apres=True, exporter_apres=True)
    plan = plan_pipeline("sharp", rs)
    assert "entrainement" not in plan
    assert plan == ["source", "reconstruction", "export"]


def test_4dgs_truncated_to_two_steps():
    rs = _rs(entrainement_apres=True, nettoyer_apres=True, visualiser_apres=True)
    assert plan_pipeline("4dgs", rs) == ["source", "reconstruction"]


def test_unknown_mode_falls_back_to_gsplat():
    assert plan_pipeline("inconnu", _rs()) == ["source", "reconstruction"]


def test_post_steps_order_independent_of_flag_setting_order():
    rs = _rs(visualiser_apres=True, nettoyer_apres=True)  # ordre inversé
    plan = plan_pipeline("gsplat", rs)
    assert plan == ["source", "reconstruction", "nettoyage", "visualiser"]
