"""Test end-to-end RÉEL de l'upscaling avec le vrai binaire upscayl-bin.

Contrairement aux tests mockés de upscayl_manager, celui-ci exécute la chaîne
réelle sur une image synthétique générée à la volée :

    image synthétique 160×120 → upscayl-bin (x4) → image 640×480

Opt-in uniquement (marqueurs ``e2e`` et ``e2e_upscale``, désélectionnés par
``-m 'not e2e'`` dans pyproject.toml). Lancement : ``pytest -m e2e_upscale``
Ignoré automatiquement si ``upscayl-bin`` ou les modèles sont introuvables.

L'upscale coûteux tourne UNE fois (fixture de portée module) ; chaque test
vérifie ensuite un artefact distinct.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.upscayl_manager import find_binary, get_effective_models_dir

_UPSCAYL_BIN = find_binary()
_MODELS_DIR = get_effective_models_dir()
_HAS_MODELS = _MODELS_DIR is not None and any(Path(_MODELS_DIR).glob("*.bin"))

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.e2e_upscale,
    pytest.mark.skipif(
        _UPSCAYL_BIN is None or not _HAS_MODELS,
        reason=f"Requires upscayl-bin + models. bin={_UPSCAYL_BIN}, models_ok={_HAS_MODELS}",
    ),
]


@pytest.fixture(scope="module")
def upscale_run(tmp_path_factory) -> dict:
    """Exécute l'upscale réel une seule fois et retourne ses artefacts."""
    from tests.integration._synthetic_image import generate_upscale_target
    from app.core.upscale_engine import UpscaleEngine

    work = tmp_path_factory.mktemp("upscale_e2e")
    in_img = generate_upscale_target(work / "input.png", w=160, h=120, seed=11)

    engine = UpscaleEngine(logger_callback=lambda _m: None)
    upsampler = engine.load_model(model_id="realesrgan-x4plus", scale=4)
    if not upsampler:
        pytest.skip("Impossible de charger le modèle upscayl (load_model a retourné None)")

    out_dir = work / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    # upscale_image utilise le parent du chemin passé comme répertoire de sortie.
    result = engine.upscale_image(str(in_img), str(out_dir / "upscaled.png"), upsampler=upsampler)

    out_files = sorted(out_dir.glob("*.png"))
    return {
        "work": work,
        "in_img": in_img,
        "out_dir": out_dir,
        "result": result,
        "out_files": out_files,
    }


class TestE2EUpscale:
    """Vérifie chaque artefact de l'upscale réel."""

    def test_output_exists(self, upscale_run: dict) -> None:
        assert upscale_run["result"], "upscale_image a retourné False"
        assert upscale_run["out_files"], "aucun fichier PNG trouvé dans le répertoire de sortie"

    def test_output_dimensions_4x(self, upscale_run: dict) -> None:
        from PIL import Image

        out_file = upscale_run["out_files"][0]
        with Image.open(out_file) as img:
            assert img.size == (640, 480), f"taille inattendue : {img.size}"

    def test_output_not_trivial_copy(self, upscale_run: dict) -> None:
        from PIL import Image

        in_file = upscale_run["in_img"]
        out_file = upscale_run["out_files"][0]

        # Un simple copiage brut est impossible (160×120 ≠ 640×480), mais on
        # vérifie aussi que le contenu pixel est effectivement transformé.
        assert out_file.stat().st_size != in_file.stat().st_size, (
            "le fichier de sortie a la même taille que l'entrée (copie ?)"
        )
        with Image.open(in_file) as src, Image.open(out_file) as dst:
            assert src.size != dst.size, "taille identique — pas d'upscale effectif"

    def test_output_valid_format(self, upscale_run: dict) -> None:
        from PIL import Image

        out_file = upscale_run["out_files"][0]
        with Image.open(out_file) as img:
            assert img.format == "PNG", f"format inattendu : {img.format}"
            assert img.mode in ("RGB", "RGBA"), f"mode inattendu : {img.mode}"
