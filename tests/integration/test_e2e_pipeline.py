"""Test end-to-end RÉEL du pipeline complet, avec les vrais binaires.

Contrairement aux autres tests d'intégration (binaires mockés), celui-ci exécute
la chaîne complète sur une scène synthétique générée à la volée :

    images synthétiques → COLMAP (SfM réel) → Brush (entraînement réel)
                        → PlyCleaner → ExportEngine (SPZ)

Opt-in uniquement (marqueur ``e2e``, désélectionné par défaut dans pyproject.toml).
Lancement :  ``pytest -m e2e``
Ignoré automatiquement si ``colmap`` ou ``brush`` sont introuvables.

Le pipeline coûteux tourne UNE fois (fixture de portée module) ; chaque test
vérifie ensuite un artefact distinct.
"""
from __future__ import annotations

import struct
from pathlib import Path

import pytest

from app.core.system import resolve_binary
from tests.integration._synthetic_scene import generate_scene

pytestmark = pytest.mark.e2e

_COLMAP = resolve_binary("colmap")
_BRUSH = resolve_binary("brush")

requires_real_binaries = pytest.mark.skipif(
    not (_COLMAP and _BRUSH),
    reason="e2e réel : nécessite les binaires colmap ET brush installés",
)

N_VIEWS = 24


def _num_registered_images(images_bin: Path) -> int:
    """Lit l'en-tête COLMAP images.bin : uint64 little-endian = nb d'images."""
    with images_bin.open("rb") as fh:
        return struct.unpack("<Q", fh.read(8))[0]


@pytest.fixture(scope="module")
def pipeline(tmp_path_factory) -> dict:
    """Exécute le pipeline complet réel une seule fois et retourne ses artefacts."""
    from app.core.brush_engine import BrushEngine
    from app.core.engine import ColmapEngine
    from app.core.export_engine import ExportEngine
    from app.core.params import ColmapParams
    from app.core.ply_cleaner import clean_ply
    from app.core.system import get_brush_build_mode

    work = tmp_path_factory.mktemp("e2e_pipeline")
    src_images = work / "src_images"
    generate_scene(src_images, n_views=N_VIEWS)

    # ── 1. COLMAP (SfM réel, défauts SIFT + brute-force + global_mapper) ──────
    colmap_out = work / "colmap_out"
    engine = ColmapEngine(
        ColmapParams(), str(src_images), str(colmap_out), "images", 1,
        project_name="synth",
        logger_callback=lambda _m: None,
        progress_callback=lambda _x: None,
    )
    colmap_ok, colmap_msg = engine.run()
    dataset = colmap_out / "synth"
    model0 = dataset / "sparse" / "0"

    # ── 2. Brush (entraînement réel, minimal) ────────────────────────────────
    brush_rc = None
    plys: list[Path] = []
    if colmap_ok and model0.is_dir():
        brush = BrushEngine(logger_callback=lambda _m: None)
        brush_params = {
            "total_steps": 200,        # minimal — smoke réel, pas qualité
            "sh_degree": 1,
            "max_resolution": 400,
            "checkpoint_interval": 0,
            "build_mode": get_brush_build_mode(),
        }
        brush_rc = brush.train(str(dataset), str(dataset), params=brush_params)
        plys = sorted(p for p in dataset.rglob("*.ply") if not p.name.startswith("."))

    # ── 3. Clean + 4. Export SPZ ─────────────────────────────────────────────
    clean_stats = None
    cleaned = work / "cleaned.ply"
    spz_ok = False
    spz_files: list[Path] = []
    if plys:
        splat = max(plys, key=lambda p: p.stat().st_mtime)
        clean_stats = clean_ply(str(splat), str(cleaned), strength="light",
                                log=lambda _m: None)
        spz_ok = ExportEngine(logger_callback=lambda _m: None).export(
            str(cleaned), str(work), "spz"
        )
        spz_files = list(work.glob("*.spz"))

    return {
        "colmap_ok": colmap_ok,
        "colmap_msg": colmap_msg,
        "model0": model0,
        "brush_rc": brush_rc,
        "plys": plys,
        "clean_stats": clean_stats,
        "cleaned": cleaned,
        "spz_ok": spz_ok,
        "spz_files": spz_files,
    }


@requires_real_binaries
class TestE2EPipeline:
    """Vérifie chaque étape de la chaîne réelle sur la scène synthétique."""

    def test_colmap_reconstruction_succeeds(self, pipeline):
        assert pipeline["colmap_ok"], f"COLMAP a échoué : {pipeline['colmap_msg']}"

    def test_sparse_model_is_valid(self, pipeline):
        model0 = pipeline["model0"]
        assert model0.is_dir(), "sparse/0 absent"
        for stem in ("cameras", "images", "points3D"):
            assert (model0 / f"{stem}.bin").exists(), f"{stem}.bin manquant"

    def test_most_images_registered(self, pipeline):
        """La reconstruction doit enregistrer la grande majorité des vues."""
        n_reg = _num_registered_images(pipeline["model0"] / "images.bin")
        assert n_reg >= int(0.8 * N_VIEWS), (
            f"seulement {n_reg}/{N_VIEWS} images enregistrées"
        )

    def test_point_cloud_is_substantial(self, pipeline):
        """points3D.bin non trivial → vraie reconstruction, pas un fragment."""
        size = (pipeline["model0"] / "points3D.bin").stat().st_size
        assert size > 10_000, f"points3D.bin trop petit ({size} octets)"

    def test_brush_produces_ply(self, pipeline):
        assert pipeline["brush_rc"] == 0, f"Brush rc={pipeline['brush_rc']}"
        assert pipeline["plys"], "aucun .ply produit par Brush"

    def test_clean_preserves_splats(self, pipeline):
        stats = pipeline["clean_stats"]
        assert stats is not None, "clean_ply non exécuté"
        assert stats["total"] > 0
        assert 0 < stats["kept"] <= stats["total"]

    def test_export_spz_created(self, pipeline):
        assert pipeline["spz_ok"], "export SPZ a échoué"
        assert pipeline["spz_files"], "aucun fichier .spz produit"
        assert pipeline["spz_files"][0].stat().st_size > 0
