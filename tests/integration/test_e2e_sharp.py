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
        from app.core.sharp_engine import SharpEngine
        from tests.integration._synthetic_image import generate_depth_image

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


class TestE2ESharpVideo:
    """End-to-end test for Sharp on video (ffmpeg extraction + per-frame prediction).

    Generates a short synthetic video (~2s, 4-5 frames), extracts frames via ffmpeg,
    runs Sharp predict on each, and verifies PLY outputs.

    Marked ``e2e`` and ``e2e_sharp``, skipped if Sharp not available or on non-Apple Silicon.
    """

    @pytest.fixture(scope="module")
    def sharp_video_run(self, tmp_path_factory):
        """Run Sharp process_video_frames on a synthetic video once per module."""
        from app.core.sharp_engine import SharpEngine
        from tests.integration._synthetic_image import generate_synthetic_video

        tmp = tmp_path_factory.mktemp("sharp_video_e2e")

        # Generate a short synthetic video: 2 seconds, 2 fps = ~4 frames
        video_path = generate_synthetic_video(
            tmp / "video_test.mp4",
            duration=2.0,
            fps=2,
            w=320,
            h=240,
        )

        out_dir = tmp / "output"
        out_dir.mkdir()

        engine = SharpEngine(logger_callback=print)

        # Call the real process_video_frames method
        success_count = engine.process_video_frames(
            video_path=str(video_path),
            output_dir=str(out_dir),
            params={},
            log_callback=print,
            status_callback=lambda s: None,
            progress_callback=lambda p: None,
            cancel_check=None,
        )

        return {
            "tmp": tmp,
            "video": video_path,
            "out_dir": out_dir,
            "success_count": success_count,
            "engine": engine,
        }

    def test_video_extraction_produces_plys(self, sharp_video_run):
        """Sharp process_video_frames should produce at least one PLY file."""
        assert sharp_video_run["success_count"] > 0, (
            f"No frames processed successfully. "
            f"Got {sharp_video_run['success_count']} successful frames."
        )

    def test_ply_files_created(self, sharp_video_run):
        """At least one .ply file should be created in the output directory."""
        ply_files = list(sharp_video_run["out_dir"].glob("*.ply"))
        assert len(ply_files) > 0, "No PLY output produced from video frames"

    def test_ply_files_valid_format(self, sharp_video_run):
        """All PLY files should have valid PLY header (start with 'ply\\n')."""
        ply_files = list(sharp_video_run["out_dir"].glob("*.ply"))
        assert ply_files, "No PLY files found"
        for ply_file in ply_files:
            content = ply_file.read_bytes()
            assert content[:4] == b"ply\n", (
                f"Invalid PLY header in {ply_file.name}: {content[:50]}"
            )

    def test_ply_files_nontrivial(self, sharp_video_run):
        """PLY files should contain meaningful data (not empty depth maps)."""
        ply_files = list(sharp_video_run["out_dir"].glob("*.ply"))
        assert ply_files, "No PLY files found"
        for ply_file in ply_files:
            content = ply_file.read_bytes()
            # Rough heuristic: non-empty depth prediction should produce PLY > 1KB
            assert len(content) > 1024, (
                f"PLY too small ({len(content)} bytes) in {ply_file.name}, "
                "likely empty depth prediction"
            )

    def test_temp_frames_cleaned_up(self, sharp_video_run):
        """Temporary frame extraction directory should be cleaned up."""
        temp_frames_dir = sharp_video_run["out_dir"] / "temp_frames"
        assert not temp_frames_dir.exists(), (
            "Temporary frames directory was not cleaned up"
        )
