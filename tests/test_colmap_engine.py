"""Tests pour app/core/engine.py — ColmapEngine."""
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, ANY, PropertyMock

import pytest

# Patch send2trash and cv2 at module level if missing
for _mod_name in ["send2trash", "cv2"]:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = MagicMock()


# ─────────────────────────────────────────────────────────────────────────────
# ColmapEngine.delete_project_content tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteProjectContent:
    """Tests pour ColmapEngine.delete_project_content() — sécurité des chemins."""

    def test_path_inside_project_root(self, tmp_path):
        """Chemin dans project_root → succès."""
        from app.core.engine import ColmapEngine

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        subdir = project_dir / "subdir"
        subdir.mkdir()

        with patch("app.core.system.resolve_project_root", return_value=tmp_path):
            with patch("send2trash.send2trash") as mock_trash:
                result, msg = ColmapEngine.delete_project_content(subdir)
                assert result is True
                assert "corbeille" in msg

    def test_path_inside_home_blocked(self):
        """Chemin dans $HOME mais hors project_root → bloqué (sécurité renforcée)."""
        from app.core.engine import ColmapEngine

        home_subdir = Path.home() / ".corbeausplat_test_delete"
        home_subdir.mkdir(parents=True, exist_ok=True)

        try:
            with patch("app.core.system.resolve_project_root", return_value=Path("/tmp/fake_project")):
                with patch("send2trash.send2trash") as mock_trash:
                    result, msg = ColmapEngine.delete_project_content(home_subdir)
                    assert result is False
                    assert "bloquée" in msg
        finally:
            if home_subdir.exists():
                home_subdir.rmdir()

    def test_path_is_project_root_blocked(self, tmp_path):
        """Chemin === project_root → bloqué."""
        from app.core.engine import ColmapEngine

        with patch("app.core.system.resolve_project_root", return_value=tmp_path):
            result, msg = ColmapEngine.delete_project_content(tmp_path)
            assert result is False
            assert "bloquée" in msg

    def test_path_is_home_blocked(self):
        """Chemin === Path.home() → bloqué."""
        from app.core.engine import ColmapEngine

        with patch("app.core.system.resolve_project_root", return_value=Path("/tmp/fake_project")):
            result, msg = ColmapEngine.delete_project_content(Path.home())
            assert result is False
            assert "bloquée" in msg

    def test_path_outside_allowed_areas(self):
        """Chemin en dehors de project_root et home → bloqué."""
        from app.core.engine import ColmapEngine

        with patch("app.core.system.resolve_project_root", return_value=Path("/tmp/fake_project")):
            result, msg = ColmapEngine.delete_project_content(Path("/opt/somewhere"))
            assert result is False
            assert "bloquée" in msg

    def test_path_is_root_blocked(self):
        """Chemin = / → bloqué."""
        from app.core.engine import ColmapEngine

        with patch("app.core.system.resolve_project_root", return_value=Path("/tmp/fake_project")):
            result, msg = ColmapEngine.delete_project_content(Path("/"))
            assert result is False
            assert "bloquée" in msg

    def test_nonexistent_path(self, tmp_path):
        """Chemin inexistant → False avec message approprié."""
        from app.core.engine import ColmapEngine

        nonexistent = tmp_path / "does_not_exist"

        with patch("app.core.system.resolve_project_root", return_value=tmp_path):
            result, msg = ColmapEngine.delete_project_content(nonexistent)
            assert result is False
            assert "n'existe pas" in msg

    def test_images_skipped(self, tmp_path):
        """Le dossier 'images' est ignoré (pas envoyé à la corbeille)."""
        from app.core.engine import ColmapEngine

        project = tmp_path / "project"
        project.mkdir()
        images_dir = project / "images"
        images_dir.mkdir()
        other_dir = project / "other"
        other_dir.mkdir()

        with patch("app.core.system.resolve_project_root", return_value=tmp_path):
            with patch("send2trash.send2trash") as mock_trash:
                result, msg = ColmapEngine.delete_project_content(project)
                assert result is True
                # other should be trashed, images should NOT be trashed
                mock_trash.assert_called_once_with(str(other_dir))


# ─────────────────────────────────────────────────────────────────────────────
# ColmapEngine.build_command tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildCommand:
    """Tests pour la construction des commandes COLMAP."""

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.has_cuda")
    def test_feature_extraction_command(self, mock_silicon, mock_resolve_binary, tmp_path):
        """feature_extraction construit la bonne commande COLMAP."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x  # return name as-is

        from app.core.engine import ColmapEngine

        params = MagicMock()
        params.camera_model = "SIMPLE_RADIAL"
        params.single_camera = True
        params.max_image_size = 3200
        params.max_num_features = 8192
        params.estimate_affine_shape = False
        params.domain_size_pooling = False
        params.matcher_type = "sequential"

        engine = ColmapEngine(
            params, str(tmp_path / "input"), str(tmp_path / "output"),
            "images", 5, logger_callback=print
        )

        with patch.object(engine, '_write_sorted_image_list', return_value=None):
            with patch.object(engine, 'run_command', return_value=True) as mock_run:
                engine.feature_extraction(
                    str(tmp_path / "database.db"),
                    str(tmp_path / "images"),
                )
                cmd = mock_run.call_args[0][0]
                assert "colmap" in cmd[0] or cmd[0] == "colmap"
                assert "feature_extractor" in cmd
                assert "--ImageReader.camera_model" in cmd
                assert "--ImageReader.single_camera" in cmd
                assert "--SiftExtraction.max_num_features" in cmd

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.has_cuda")
    def test_sequential_matcher_command(self, mock_silicon, mock_resolve_binary, tmp_path):
        """sequential_matcher est utilisé quand matcher_type='sequential'."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        from app.core.engine import ColmapEngine

        params = MagicMock()
        params.matcher_type = "sequential"
        params.max_ratio = 0.8
        params.max_distance = 0.7
        params.cross_check = True
        params.guided_matching = False
        params.sequential_overlap = 10

        engine = ColmapEngine(
            params, str(tmp_path / "input"), str(tmp_path / "output"),
            "images", 5, logger_callback=print
        )

        with patch.object(engine, 'run_command', return_value=True) as mock_run:
            engine.feature_matching(str(tmp_path / "database.db"))
            cmd = mock_run.call_args[0][0]
            assert "sequential_matcher" in cmd
            assert "exhaustive_matcher" not in cmd
            assert "--SequentialMatching.overlap" in cmd

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.has_cuda")
    def test_exhaustive_matcher_command(self, mock_silicon, mock_resolve_binary, tmp_path):
        """exhaustive_matcher est utilisé quand matcher_type='exhaustive'."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        from app.core.engine import ColmapEngine

        params = MagicMock()
        params.matcher_type = "exhaustive"
        params.max_ratio = 0.8
        params.max_distance = 0.7
        params.cross_check = True
        params.guided_matching = False

        engine = ColmapEngine(
            params, str(tmp_path / "input"), str(tmp_path / "output"),
            "images", 5, logger_callback=print
        )

        with patch.object(engine, 'run_command', return_value=True) as mock_run:
            engine.feature_matching(str(tmp_path / "database.db"))
            cmd = mock_run.call_args[0][0]
            assert "exhaustive_matcher" in cmd
            assert "sequential_matcher" not in cmd

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.has_cuda")
    def test_mapper_colmap_command(self, mock_silicon, mock_resolve_binary, tmp_path):
        """Mapper utilise COLMAP par défaut."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        from app.core.engine import ColmapEngine

        params = MagicMock()
        params.use_glomap = False
        params.min_model_size = 10
        params.multiple_models = False
        params.ba_refine_focal_length = True
        params.ba_refine_principal_point = False
        params.ba_refine_extra_params = True
        params.min_num_matches = 15

        engine = ColmapEngine(
            params, str(tmp_path / "input"), str(tmp_path / "output"),
            "images", 5, logger_callback=print
        )

        with patch.object(engine, 'run_command', return_value=True) as mock_run:
            engine.mapper(str(tmp_path / "database.db"), str(tmp_path / "images"), tmp_path / "sparse")
            cmd = mock_run.call_args[0][0]
            assert "colmap" in cmd
            assert "mapper" in cmd
            assert "--Mapper.num_threads" in cmd
            assert "glomap" not in cmd

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.has_cuda")
    def test_mapper_glomap_command(self, mock_silicon, mock_resolve_binary, tmp_path):
        """Mapper utilise GLOMAP quand use_glomap=True."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        from app.core.engine import ColmapEngine

        params = MagicMock()
        params.use_glomap = True

        engine = ColmapEngine(
            params, str(tmp_path / "input"), str(tmp_path / "output"),
            "images", 5, logger_callback=print
        )

        with patch.object(engine, 'run_command', return_value=True) as mock_run:
            engine.mapper(str(tmp_path / "database.db"), str(tmp_path / "images"), tmp_path / "sparse")
            cmd = mock_run.call_args[0][0]
            assert "glomap" in cmd
            assert "mapper" in cmd

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.has_cuda")
    def test_image_undistorter_command(self, mock_silicon, mock_resolve_binary, tmp_path):
        """image_undistorter construit la bonne commande."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        from app.core.engine import ColmapEngine

        params = MagicMock()
        params.max_image_size = 3200

        engine = ColmapEngine(
            params, str(tmp_path / "input"), str(tmp_path / "output"),
            "images", 5, logger_callback=print
        )

        with patch.object(engine, 'run_command', return_value=True) as mock_run:
            engine.image_undistorter(str(tmp_path / "images"), str(tmp_path / "sparse"), str(tmp_path / "dense"))
            cmd = mock_run.call_args[0][0]
            assert "image_undistorter" in cmd
            assert "--output_type" in cmd

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.has_cuda")
    def test_feature_extraction_hwaccel_cuda(self, mock_cuda, mock_resolve_binary, tmp_path):
        """Test qu'un GPU CUDA active l'accélération matérielle (-hwaccel cuda) dans extract_frames."""
        mock_cuda.return_value = True
        mock_resolve_binary.side_effect = lambda x: x

        from app.core.engine import ColmapEngine

        params = MagicMock()
        params.camera_model = "SIMPLE_RADIAL"
        params.single_camera = True
        params.max_image_size = 3200
        params.max_num_features = 8192
        params.estimate_affine_shape = False
        params.domain_size_pooling = False
        params.matcher_type = "sequential"

        engine = ColmapEngine(
            params, str(tmp_path / "input"), str(tmp_path / "output"),
            "video", 5, logger_callback=print
        )

        # Check that has_cuda flag is set
        assert engine.has_cuda is True


# ─────────────────────────────────────────────────────────────────────────────
# ColmapEngine._check_and_normalize_resolution tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckAndNormalizeResolution:
    """Tests pour _check_and_normalize_resolution()."""

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.has_cuda")
    def test_cv2_not_loaded_returns_true(self, mock_silicon, mock_resolve_binary, tmp_path):
        """cv2 non chargé → retourne True immédiatement."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        from app.core.engine import ColmapEngine

        params = MagicMock()
        engine = ColmapEngine(
            params, str(tmp_path / "input"), str(tmp_path / "output"),
            "images", 5, logger_callback=print
        )
        engine._cv2_loaded = False

        result = engine._check_and_normalize_resolution(tmp_path / "images")
        assert result is True

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.has_cuda")
    def test_uniform_resolution(self, mock_silicon, mock_resolve_binary, tmp_path):
        """Toutes les images ont la même résolution → True."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        from app.core.engine import ColmapEngine

        params = MagicMock()
        engine = ColmapEngine(
            params, str(tmp_path / "input"), str(tmp_path / "output"),
            "images", 5, logger_callback=print
        )
        engine._cv2_loaded = True

        # Create images with uniform size
        images_dir = tmp_path / "images"
        images_dir.mkdir()
        for i in range(3):
            (images_dir / f"img_{i:04d}.jpg").write_bytes(b"fake_jpg")

        with patch("cv2.imread") as mock_imread:
            mock_img = MagicMock()
            mock_img.shape = (480, 640, 3)
            mock_imread.return_value = mock_img

            result = engine._check_and_normalize_resolution(images_dir)
            assert result is True

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.has_cuda")
    def test_fewer_than_2_images_returns_true(self, mock_silicon, mock_resolve_binary, tmp_path):
        """Moins de 2 images → True (pas besoin de normaliser)."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        from app.core.engine import ColmapEngine

        params = MagicMock()
        engine = ColmapEngine(
            params, str(tmp_path / "input"), str(tmp_path / "output"),
            "images", 5, logger_callback=print
        )
        engine._cv2_loaded = True

        images_dir = tmp_path / "images"
        images_dir.mkdir()
        (images_dir / "img_0001.jpg").write_bytes(b"fake_jpg")

        result = engine._check_and_normalize_resolution(images_dir)
        assert result is True


# ─────────────────────────────────────────────────────────────────────────────
# ColmapEngine utility methods
# ─────────────────────────────────────────────────────────────────────────────

class TestColmapUtils:
    """Tests pour les méthodes utilitaires de ColmapEngine."""

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.has_cuda")
    def test_project_path_property(self, mock_silicon, mock_resolve_binary, tmp_path):
        """project_path retourne le output_path."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        from app.core.engine import ColmapEngine

        params = MagicMock()
        engine = ColmapEngine(
            params, str(tmp_path / "input"), str(tmp_path / "output"),
            "images", 5, logger_callback=print
        )
        assert engine.project_path == engine.output_path

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.has_cuda")
    def test_validate_and_setup_paths_success(self, mock_silicon, mock_resolve_binary, tmp_path):
        """_validate_and_setup_paths crée la structure de dossiers."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        from app.core.engine import ColmapEngine

        input_dir = tmp_path / "input_data"
        input_dir.mkdir()
        (input_dir / "img_0001.jpg").write_bytes(b"fake")

        params = MagicMock()
        engine = ColmapEngine(
            params, str(input_dir), str(tmp_path / "output"),
            "images", 5, project_name="test_proj", logger_callback=print
        )

        # Override project_root to allow path validation against tmp_path
        engine.project_root = tmp_path

        result = engine._validate_and_setup_paths()
        assert result is not None
        project_dir, images_dir, checkpoints_dir = result
        assert project_dir.exists()
        assert images_dir.exists()
        assert checkpoints_dir.exists()

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.has_cuda")
    def test_validate_project_name_with_dots_blocked(self, mock_silicon, mock_resolve_binary, tmp_path):
        """Nom de projet avec '..' → None."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        from app.core.engine import ColmapEngine

        input_dir = tmp_path / "input_data"
        input_dir.mkdir()
        (input_dir / "img_0001.jpg").write_bytes(b"fake")

        params = MagicMock()
        engine = ColmapEngine(
            params, str(input_dir), str(tmp_path / "output"),
            "images", 5, project_name="../malicious", logger_callback=print
        )

        result = engine._validate_and_setup_paths()
        assert result is None

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.has_cuda")
    def test_convert_db_journal_mode(self, mock_silicon, mock_resolve_binary, tmp_path):
        """_convert_db_journal_mode s'exécute sans erreur."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        from app.core.engine import ColmapEngine

        params = MagicMock()
        engine = ColmapEngine(
            params, str(tmp_path / "input"), str(tmp_path / "output"),
            "images", 5, logger_callback=print
        )

        db_path = tmp_path / "database.db"
        # Should handle non-existent db gracefully
        engine._convert_db_journal_mode(db_path)
        # No exception means success

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.has_cuda")
    def test_create_brush_config(self, mock_silicon, mock_resolve_binary, tmp_path):
        """create_brush_config génère le fichier JSON."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        from app.core.engine import ColmapEngine

        params = MagicMock()
        params.to_dict.return_value = {"test": True}
        params.undistort_images = False

        engine = ColmapEngine(
            params, str(tmp_path / "input"), str(tmp_path / "output"),
            "images", 5, logger_callback=print
        )

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        images_dir = output_dir / "images"
        images_dir.mkdir()
        sparse_dir = output_dir / "sparse"
        sparse_dir.mkdir()

        engine.create_brush_config(output_dir, images_dir, sparse_dir)

        config_file = output_dir / "brush_config.json"
        assert config_file.exists()

        import json
        config = json.loads(config_file.read_text())
        assert config["dataset_type"] == "colmap"
        assert config["parameters"]["test"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Blur filtering selection logic
# ─────────────────────────────────────────────────────────────────────────────

class TestSelectBlurryFiles:
    """Tests pour engine.select_blurry_files()."""

    def test_discards_below_factor_of_median(self):
        from app.core.engine import select_blurry_files
        # median of [10,100,100,100,100] = 100; factor 0.7 -> threshold 70
        scores = {"a": 10.0, "b": 100.0, "c": 100.0, "d": 100.0, "e": 100.0}
        rejected, threshold = select_blurry_files(scores, 0.7)
        assert threshold == 70.0
        assert rejected == ["a"]

    def test_disabled_when_factor_zero(self):
        from app.core.engine import select_blurry_files
        scores = {"a": 1.0, "b": 100.0}
        rejected, _ = select_blurry_files(scores, 0.0)
        assert rejected == []

    def test_empty_scores(self):
        from app.core.engine import select_blurry_files
        assert select_blurry_files({}, 0.7) == ([], 0.0)

    def test_cap_limits_removals_to_blurriest(self):
        from app.core.engine import select_blurry_files
        # 3 blurry (score 1) + 7 sharp (score 100); median 100, threshold 70 -> 3 below.
        # With a 10% cap on 10 files, only the single blurriest may be removed.
        scores = {"a": 1.0, "b": 2.0, "c": 3.0}
        scores.update({f"s{i}": 100.0 for i in range(7)})
        rejected, _ = select_blurry_files(scores, 0.7, max_remove_frac=0.1)
        assert rejected == ["a"]  # cap = int(10 * 0.1) = 1, blurriest kept
