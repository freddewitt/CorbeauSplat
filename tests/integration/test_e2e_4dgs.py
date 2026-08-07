"""Test end-to-end RÉEL du moteur 4DGS en mode COLMAP dégradé.

Sans le venv `.venv_4dgs` ce test exécute quand même le tronçon
vidéos → frames → COLMAP (feature_extractor / matcher / mapper).
Opt-in par le marqueur ``e2e_4dgs`` (désélectionné par défaut).
"""
from __future__ import annotations

import struct
from pathlib import Path

import pytest

from app.core.system import resolve_binary

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_4dgs]


def _fourdgs_ready() -> tuple[bool, str]:
    missing = []
    if not resolve_binary("ffmpeg"):
        missing.append("ffmpeg")
    if not resolve_binary("colmap"):
        missing.append("colmap")
    if missing:
        return False, f"manque: {', '.join(missing)}"
    return True, "4DGS COLMAP prêt"


_READY, _REASON = _fourdgs_ready()

requires_fourdgs_colmap = pytest.mark.skipif(
    not _READY,
    reason=f"e2e 4DGS Phase A : {_REASON}",
)


def _num_registered_images(images_bin: Path) -> int:
    """Lit l'en-tête COLMAP images.bin : uint64 little-endian = nb d'images."""
    with images_bin.open("rb") as fh:
        return struct.unpack("<Q", fh.read(8))[0]


@requires_fourdgs_colmap
class TestE2E4DGS:
    """Vérifie le mode dégradé COLMAP du FourDGSEngine sur données synthétiques."""

    @pytest.fixture(scope="module")
    def fourdgs_run(self, tmp_path_factory):
        from app.core.four_dgs_engine import FourDGSEngine
        from tests.integration._synthetic_video import generate_multi_cam_videos

        tmp = tmp_path_factory.mktemp("fourdgs_e2e")

        # Generate single-cam video (1 cam, 48 frames = 48 total views)
        videos_dir = tmp / "videos"
        videos_dir.mkdir()
        video_paths = generate_multi_cam_videos(
            out_dir=videos_dir, n_cams=1, n_frames=48, w=1024, h=768, fps=5, seed=7
        )

        output_dir = tmp / "output"
        output_dir.mkdir()

        engine = FourDGSEngine(logger_callback=print, status_callback=lambda s: None)
        result = engine.process_dataset(str(videos_dir), str(output_dir), fps=5)

        return {
            "tmp": tmp,
            "videos_dir": videos_dir,
            "output_dir": output_dir,
            "result": result,
            "engine": engine,
            "video_paths": video_paths,
        }

    def test_returns_true(self, fourdgs_run):
        assert fourdgs_run["result"] is True

    def test_extracted_frames_per_camera(self, fourdgs_run):
        images_dir = fourdgs_run["output_dir"] / "images"
        cam_dirs = sorted(d for d in images_dir.iterdir() if d.is_dir())
        assert len(cam_dirs) >= 1, "aucun dossier de frames extrait"
        for cam_dir in cam_dirs:
            frames = list(cam_dir.glob("*.jpg"))
            assert len(frames) >= 12, (
                f"{cam_dir.name}: seulement {len(frames)} frames extraites"
            )

    def test_colmap_sparse_model_built(self, fourdgs_run):
        model0 = fourdgs_run["output_dir"] / "sparse" / "0"
        assert model0.is_dir(), "sparse/0 absent"
        for stem in ("cameras", "images", "points3D"):
            assert (model0 / f"{stem}.bin").exists(), f"{stem}.bin manquant"

    def test_sparse_model_nontrivial(self, fourdgs_run):
        images_bin = fourdgs_run["output_dir"] / "sparse" / "0" / "images.bin"
        n_reg = _num_registered_images(images_bin)
        assert n_reg >= 3, f"seulement {n_reg} images enregistrées"
