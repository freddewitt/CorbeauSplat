"""Test end-to-end RÉEL de Sharp (Apple ML Depth) sur une image synthétique.

Contrairement aux tests mockés de sharp_engine, celui-ci exécute la prédiction
réelle avec le vrai binaire/module Sharp :

    image synthétique 640×480 → Sharp predict → nuage de points PLY

Opt-in uniquement (marqueurs ``e2e`` et ``e2e_sharp``, désélectionnés par
``-m 'not e2e'`` dans pyproject.toml). Lancement : ``pytest -m e2e_sharp``
Ignoré automatiquement si .venv_sharp est absent ou si le système n'est pas
Apple Silicon.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.core.system import is_apple_silicon, resolve_project_root


def _sharp_ready() -> tuple[bool, str]:
    """Vérifie que Sharp est exécutable (venv + binaire/module + Apple Silicon)."""
    if not is_apple_silicon():
        return False, "Apple Silicon required for Sharp"

    root = resolve_project_root()
    venv_sharp = root / ".venv_sharp"
    if not venv_sharp.exists():
        return False, ".venv_sharp not found"

    sharp_bin = venv_sharp / "bin" / "sharp"
    if not sharp_bin.exists() and not shutil.which("sharp"):
        # Dernier recours : module sharp importable depuis l'environnement courant
        try:
            import importlib.util

            if importlib.util.find_spec("sharp") is None:
                return False, "sharp binary/module not found"
        except Exception:
            return False, "sharp binary/module not found"

    from app.core.sharp_engine import SharpEngine

    engine = SharpEngine(logger_callback=lambda _m: None)
    if not engine.is_installed():
        return False, "Sharp engine reports not installed"

    if sharp_bin.exists():
        return True, f"sharp venv binary: {sharp_bin}"
    if shutil.which("sharp"):
        return True, f"sharp on PATH: {shutil.which('sharp')}"
    return True, "sharp module available"


_SHARP_OK, _SHARP_REASON = _sharp_ready()

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.e2e_sharp,
    pytest.mark.skipif(not _SHARP_OK, reason=f"e2e Sharp: {_SHARP_REASON}"),
]


class TestE2ESharpImage:
    @pytest.fixture(scope="module")
    def sharp_run(self, tmp_path_factory):
        """Run Sharp predict on a synthetic depth image once per module."""
        from tests.integration._synthetic_image import generate_depth_image
        from app.core.sharp_engine import SharpEngine

        tmp = tmp_path_factory.mktemp("sharp_e2e")
        img = generate_depth_image(tmp / "depth_test.png", w=640, h=480, seed=7)

        out_dir = tmp / "output"
        out_dir.mkdir()

        engine = SharpEngine(logger_callback=print)
        result = engine.predict(str(img), str(out_dir))

        return {"tmp": tmp, "img": img, "out_dir": out_dir, "result": result, "engine": engine}

    def test_returns_zero(self, sharp_run):
        """Sharp predict should return 0 (success)."""
        assert sharp_run["result"] == 0

    def test_ply_produced(self, sharp_run):
        """At least one .ply file should be produced."""
        ply_files = list(sharp_run["out_dir"].glob("*.ply"))
        assert len(ply_files) > 0, "No PLY output produced"

    def test_ply_has_valid_header(self, sharp_run):
        """PLY file should have a valid header."""
        ply_files = list(sharp_run["out_dir"].glob("*.ply"))
        assert ply_files, "No PLY files found"
        content = ply_files[0].read_bytes()
        # PLY header starts with "ply\n"
        assert content[:4] == b"ply\n", f"Invalid PLY header: {content[:50]}"

    def test_ply_nontrivial_point_count(self, sharp_run):
        """PLY should contain a meaningful number of points (> 100)."""
        ply_files = list(sharp_run["out_dir"].glob("*.ply"))
        assert ply_files, "No PLY files found"
        content = ply_files[0].read_bytes()
        # Rough check: file should be > 1KB for a non-trivial depth map
        assert len(content) > 1024, f"PLY too small ({len(content)} bytes), likely empty depth"
