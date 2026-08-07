"""Test end-to-end RÉEL de 360 Extractor sur une image équirectangulaire synthétique.

Contrairement aux tests mockés de test_extractor_360_engine.py, celui-ci exécute
l'extraction réelle avec le vrai binaire 360Extractor :

    image équirectangulaire 1024×512 → 360Extractor → images planaires

Opt-in uniquement (marqueur ``e2e_360``, désélectionné par défaut).
Lancement : ``pytest -m e2e_360``
Ignoré automatiquement si .venv_360 est absent ou si le script 360Extractor n'est pas installé.
"""
from __future__ import annotations

import pytest
from PIL import Image


def _extractor_360_ready() -> tuple[bool, str]:
    """Vérifie que 360Extractor est exécutable (venv + script)."""
    from app.core.extractor_360_engine import Extractor360Engine

    engine = Extractor360Engine(logger_callback=lambda _m: None)
    if not engine.is_installed():
        return False, ".venv_360 ou script 360Extractor absent"
    return True, "360Extractor prêt"


_EXTRACTOR_READY, _EXTRACTOR_REASON = _extractor_360_ready()

pytestmark = [
    pytest.mark.e2e_360,
    pytest.mark.skipif(not _EXTRACTOR_READY, reason=f"e2e 360: {_EXTRACTOR_REASON}"),
]


class TestE2E360ExtractorImage:
    """Tests e2e réels sur image équirectangulaire synthétique."""

    @pytest.fixture(scope="module")
    def extractor_run(self, tmp_path_factory):
        """Run 360 extraction on a synthetic equirectangular image once per module."""
        from app.core.extractor_360_engine import Extractor360Engine
        from tests.integration._synthetic_image import generate_equirectangular_image

        tmp = tmp_path_factory.mktemp("extractor360_e2e")

        # Generate equirectangular image (1024×512, 2:1 ratio, with markers)
        img_path = tmp / "equi_test.png"
        generate_equirectangular_image(img_path, w=1024, h=512, seed=13)

        out_dir = tmp / "output"
        out_dir.mkdir()

        engine = Extractor360Engine(logger_callback=lambda m: None)
        params = {
            "camera_count": 4,
            "resolution": 256,
            "format": "jpg",
            "layout": "ring",
        }
        result = engine.run_extraction(str(img_path), str(out_dir), params)

        return {
            "tmp": tmp,
            "img": img_path,
            "out_dir": out_dir,
            "result": result,
            "engine": engine,
        }

    def test_returns_true(self, extractor_run):
        """run_extraction should return True (success)."""
        assert extractor_run["result"] is True, (
            f"Expected True, got {extractor_run['result']}"
        )

    def test_output_images_count(self, extractor_run):
        """Should produce at least camera_count output images."""
        out_dir = extractor_run["out_dir"]
        images = sorted(out_dir.rglob("*.jpg"))
        assert len(images) >= 4, f"Expected >=4 images, got {len(images)}"

    def test_output_images_not_equirectangular(self, extractor_run):
        """Output images should be planar (not 2:1 equirectangular ratio)."""
        out_dir = extractor_run["out_dir"]
        images = sorted(out_dir.rglob("*.jpg"))
        assert images, "No output images found"
        for img_path in images:
            with Image.open(img_path) as img:
                w, h = img.size
                ratio = w / h if h > 0 else 0
                # Equirectangular is 2:1 — output should NOT have that ratio
                assert not (1.8 < ratio < 2.2), (
                    f"Image {img_path.name} has equirectangular-like ratio {ratio:.2f} "
                    f"({w}×{h}), expected planar"
                )

    def test_output_resolution_rough(self, extractor_run):
        """Output images should roughly match requested resolution (256px)."""
        out_dir = extractor_run["out_dir"]
        images = sorted(out_dir.rglob("*.jpg"))
        assert images, "No output images found"
        with Image.open(images[0]) as img:
            w, h = img.size
            # Allow ±20% tolerance
            assert 200 <= w <= 320, (
                f"Output width {w} not in [200,320] for resolution=256"
            )
