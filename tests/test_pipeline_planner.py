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
    rs = _rs(source_360=True, upscaler_avant=True, entrainement_apres=True,
             nettoyer_apres=True, exporter_apres=True, visualiser_apres=True)
    assert plan_pipeline("gsplat", rs) == [
        "source", "extraction360", "upscale", "reconstruction", "entrainement",
        "nettoyage", "export", "visualiser",
    ]


def test_extraction360_absent_by_default():
    assert "extraction360" not in plan_pipeline("gsplat", _rs())


def test_extraction360_runs_first_of_the_pre_steps():
    """L'extraction 360 produit le dossier d'images que l'upscale agrandit et que
    COLMAP lit : elle doit précéder les deux."""
    plan = plan_pipeline("gsplat", _rs(source_360=True))
    assert plan == ["source", "extraction360", "reconstruction"]


def test_extraction360_then_upscale_then_reconstruction():
    plan = plan_pipeline("gsplat", _rs(source_360=True, upscaler_avant=True))
    assert plan == ["source", "extraction360", "upscale", "reconstruction"]


def test_extraction360_applies_to_sharp_mode():
    plan = plan_pipeline("sharp", _rs(source_360=True))
    assert plan == ["source", "extraction360", "reconstruction"]


def test_extraction360_survives_4dgs_truncation():
    rs = _rs(source_360=True, upscaler_avant=True, entrainement_apres=True)
    assert plan_pipeline("4dgs", rs) == ["source", "extraction360", "upscale", "reconstruction"]


def test_upscale_absent_by_default():
    assert "upscale" not in plan_pipeline("gsplat", _rs())


def test_upscale_runs_before_reconstruction():
    """L'upscale agrandit les images que COLMAP lira : il doit précéder
    Reconstruction, sinon il s'appliquerait à des images déjà consommées."""
    plan = plan_pipeline("gsplat", _rs(upscaler_avant=True))
    assert plan == ["source", "upscale", "reconstruction"]


def test_upscale_applies_to_sharp_mode():
    plan = plan_pipeline("sharp", _rs(upscaler_avant=True))
    assert plan == ["source", "upscale", "reconstruction"]


def test_upscale_survives_4dgs_truncation():
    """4DGS tronque *après* Reconstruction, mais la pré-étape reste."""
    rs = _rs(upscaler_avant=True, entrainement_apres=True, visualiser_apres=True)
    assert plan_pipeline("4dgs", rs) == ["source", "upscale", "reconstruction"]


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
