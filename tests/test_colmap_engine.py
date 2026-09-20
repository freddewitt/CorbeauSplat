"""Tests for app/core/engine.py — ColmapEngine.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Provide send2trash / cv2 stubs ONLY when the real package is unavailable
# (headless CI). Injecting a MagicMock unconditionally would clobber a real,
# installed cv2 for the whole session and break other tests (e.g. the COLMAP
# integration pipeline relies on real cv2.imread).
for _mod_name in ["send2trash", "cv2"]:
    if _mod_name not in sys.modules:
        try:
            __import__(_mod_name)
        except ImportError:
            sys.modules[_mod_name] = MagicMock()


# ─────────────────────────────────────────────────────────────────────────────
# ColmapEngine.delete_project_content tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDeleteProjectContent:
    """Tests for ColmapEngine.delete_project_content() — path safety."""

    def test_path_inside_project_root(self, tmp_path):
        """Path inside project_root → success."""
        from app.core.engine import ColmapEngine

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        subdir = project_dir / "subdir"
        subdir.mkdir()

        with patch("app.core.system.resolve_project_root", return_value=tmp_path):
            with patch("app.core.engine.send2trash.send2trash"):
                result, msg = ColmapEngine.delete_project_content(subdir)
                assert result is True
                assert "corbeille" in msg

    def test_path_inside_home_allowed(self):
        """Minimal guard: an ordinary (non-critical) sub-folder of $HOME is
        allowed — the normal case of a user project.
        """
        from app.core.engine import ColmapEngine

        home_subdir = Path.home() / ".corbeausplat_test_delete"
        home_subdir.mkdir(parents=True, exist_ok=True)

        try:
            with patch("app.core.system.resolve_project_root", return_value=Path("/tmp/fake_project")):
                with patch("app.core.engine.send2trash.send2trash"):
                    result, msg = ColmapEngine.delete_project_content(home_subdir)
                    assert result is True
                    assert "bloquée" not in msg
        finally:
            if home_subdir.exists():
                home_subdir.rmdir()

    def test_path_is_project_root_blocked(self, tmp_path):
        """Path === project_root → blocked."""
        from app.core.engine import ColmapEngine

        with patch("app.core.system.resolve_project_root", return_value=tmp_path):
            result, msg = ColmapEngine.delete_project_content(tmp_path)
            assert result is False
            assert "bloquée" in msg

    def test_path_is_home_blocked(self):
        """Path === Path.home() → blocked."""
        from app.core.engine import ColmapEngine

        with patch("app.core.system.resolve_project_root", return_value=Path("/tmp/fake_project")):
            result, msg = ColmapEngine.delete_project_content(Path.home())
            assert result is False
            assert "bloquée" in msg

    def test_path_outside_home_not_security_blocked(self):
        """Minimal guard: a non-critical path outside $HOME is NOT blocked for
        security reasons. Here it does not exist → "does not exist" message, not
        "blocked".
        """
        from app.core.engine import ColmapEngine

        with patch("app.core.system.resolve_project_root", return_value=Path("/tmp/fake_project")):
            result, msg = ColmapEngine.delete_project_content(Path("/opt/nonexistent_corbeausplat"))
            assert result is False
            assert "bloquée" not in msg
            assert "n'existe pas" in msg

    def test_path_ancestor_of_home_blocked(self):
        """An ancestor of $HOME (e.g. /Users) is catastrophic → blocked."""
        from app.core.engine import ColmapEngine

        ancestor = Path.home().resolve().parent  # e.g. /Users
        with patch("app.core.system.resolve_project_root", return_value=Path("/tmp/fake_project")):
            result, msg = ColmapEngine.delete_project_content(ancestor)
            assert result is False
            assert "bloquée" in msg

    def test_path_is_root_blocked(self):
        """Path = / → blocked."""
        from app.core.engine import ColmapEngine

        with patch("app.core.system.resolve_project_root", return_value=Path("/tmp/fake_project")):
            result, msg = ColmapEngine.delete_project_content(Path("/"))
            assert result is False
            assert "bloquée" in msg

    def test_nonexistent_path(self, tmp_path):
        """Non-existent path → False with an appropriate message."""
        from app.core.engine import ColmapEngine

        nonexistent = tmp_path / "does_not_exist"

        with patch("app.core.system.resolve_project_root", return_value=tmp_path):
            result, msg = ColmapEngine.delete_project_content(nonexistent)
            assert result is False
            assert "n'existe pas" in msg

    def test_existing_path_outside_both_roots_is_deleted(self, tmp_path):
        """An existing folder outside project_root *and* $HOME is deleted, not refused.

        This pins the real contract against the docstring that used to claim a
        whitelist ("only if contained within project_root or user home"). The
        guard is a blacklist, and projects on external volumes must stay
        deletable, so acceptance here is the intended behaviour — not a gap.
        """
        from app.core.engine import ColmapEngine

        outside = tmp_path / "volume" / "scene"
        outside.mkdir(parents=True)
        junk = outside / "sparse"
        junk.mkdir()

        fake_root = tmp_path / "elsewhere" / "app"
        fake_root.mkdir(parents=True)

        with patch("app.core.system.resolve_project_root", return_value=fake_root):
            with patch("app.core.engine.Path.home", return_value=tmp_path / "elsewhere" / "home"):
                with patch("app.core.engine.send2trash.send2trash") as mock_trash:
                    result, msg = ColmapEngine.delete_project_content(outside)

        assert result is True
        assert "bloquée" not in msg
        mock_trash.assert_called_once_with(str(junk))

    def test_images_skipped(self, tmp_path):
        """The 'images' folder is skipped (not sent to the trash)."""
        from app.core.engine import ColmapEngine

        project = tmp_path / "project"
        project.mkdir()
        images_dir = project / "images"
        images_dir.mkdir()
        other_dir = project / "other"
        other_dir.mkdir()

        with patch("app.core.system.resolve_project_root", return_value=tmp_path):
            with patch("app.core.engine.send2trash.send2trash") as mock_trash:
                result, msg = ColmapEngine.delete_project_content(project)
                assert result is True
                # other should be trashed, images should NOT be trashed
                mock_trash.assert_called_once_with(str(other_dir))


# ─────────────────────────────────────────────────────────────────────────────
# ColmapEngine.build_command tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildCommand:
    """Tests for the construction of the COLMAP commands."""

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.is_apple_silicon")
    def test_feature_extraction_command(self, mock_silicon, mock_resolve_binary, tmp_path):
        """feature_extraction builds the right COLMAP command."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x  # return name as-is

        from app.core.engine import ColmapEngine

        params = MagicMock()
        params.camera_model = "SIMPLE_RADIAL"
        params.single_camera = True
        params.max_image_size = 3200
        params.max_num_features = 8192
        params.feature_type = "SIFT"
        params.matching_type = "SIFT_BRUTEFORCE"
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
    @patch("app.core.engine.is_apple_silicon")
    def test_sequential_matcher_command(self, mock_silicon, mock_resolve_binary, tmp_path):
        """sequential_matcher is used when matcher_type='sequential'."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        from app.core.engine import ColmapEngine

        params = MagicMock()
        params.matching_type = "SIFT_BRUTEFORCE"
        params.feature_type = "SIFT"
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
    @patch("app.core.engine.is_apple_silicon")
    def test_exhaustive_matcher_command(self, mock_silicon, mock_resolve_binary, tmp_path):
        """exhaustive_matcher is used when matcher_type='exhaustive'."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        from app.core.engine import ColmapEngine

        params = MagicMock()
        params.matching_type = "SIFT_BRUTEFORCE"
        params.feature_type = "SIFT"
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
    @patch("app.core.engine.is_apple_silicon")
    def test_mapper_colmap_command(self, mock_silicon, mock_resolve_binary, tmp_path):
        """Mapper uses global_mapper (COLMAP 4.0+)."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        from app.core.engine import ColmapEngine

        params = MagicMock()
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
            # 1st call: global mapper (GLOMAP)
            global_cmd = mock_run.call_args_list[0][0][0]
            assert "colmap" in global_cmd
            assert "global_mapper" in global_cmd
            assert "--GlobalMapper.num_threads" in global_cmd
            assert "glomap" not in global_cmd
            # mocked run_command returns True but no valid sparse/0 model is
            # produced → automatic fallback on the incremental mapper.
            fallback_cmd = mock_run.call_args_list[1][0][0]
            assert "mapper" in fallback_cmd
            assert "--Mapper.num_threads" in fallback_cmd

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.is_apple_silicon")
    def test_image_undistorter_command(self, mock_silicon, mock_resolve_binary, tmp_path):
        """image_undistorter builds the right command."""
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
    @patch("app.core.engine.is_apple_silicon")
    def test_feature_extraction_hwaccel_apple_silicon(self, mock_silicon, mock_resolve_binary, tmp_path):
        """Test that Apple Silicon enables hardware acceleration through videotoolbox in extract_frames."""
        mock_silicon.return_value = True
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

        # Check that is_silicon flag is set
        assert engine.is_silicon is True


# ─────────────────────────────────────────────────────────────────────────────
# ColmapEngine._check_and_normalize_resolution tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckAndNormalizeResolution:
    """Tests for _check_and_normalize_resolution()."""

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.is_apple_silicon")
    def test_cv2_not_loaded_returns_true(self, mock_silicon, mock_resolve_binary, tmp_path):
        """cv2 not loaded → returns True immediately."""
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
    @patch("app.core.engine.is_apple_silicon")
    def test_uniform_resolution(self, mock_silicon, mock_resolve_binary, tmp_path):
        """Every image has the same resolution → True."""
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
    @patch("app.core.engine.is_apple_silicon")
    def test_fewer_than_2_images_returns_true(self, mock_silicon, mock_resolve_binary, tmp_path):
        """Fewer than 2 images → True (no normalisation needed)."""
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
    """Tests for the utility methods of ColmapEngine."""

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.is_apple_silicon")
    def test_project_path_property(self, mock_silicon, mock_resolve_binary, tmp_path):
        """project_path returns the output_path."""
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
    @patch("app.core.engine.is_apple_silicon")
    def test_validate_and_setup_paths_success(self, mock_silicon, mock_resolve_binary, tmp_path):
        """_validate_and_setup_paths creates the folder structure."""
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
    @patch("app.core.engine.is_apple_silicon")
    def test_resume_colmap_skips_process_input(self, mock_silicon, mock_resolve_binary, tmp_path):
        """resume_colmap=True → skips _process_input and reuses the existing images."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x
        from app.core.engine import ColmapEngine

        output = tmp_path / "output"
        images_dir = output / "proj" / "images"
        images_dir.mkdir(parents=True)
        (images_dir / "img_0001.jpg").write_bytes(b"fake")

        engine = ColmapEngine(
            MagicMock(), str(images_dir), str(output),
            "images", 5, project_name="proj", logger_callback=print
        )
        engine.project_root = tmp_path
        engine.resume_colmap = True

        with patch.object(engine, "_process_input") as mock_process, \
             patch.object(engine, "_run_reconstruction_pipeline", return_value=(True, "ok")) as mock_pipeline:
            ok, _msg = engine.run()

        assert ok is True
        mock_process.assert_not_called()
        mock_pipeline.assert_called_once()

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.is_apple_silicon")
    def test_resume_colmap_no_images_fails(self, mock_silicon, mock_resolve_binary, tmp_path):
        """resume_colmap=True with no image → explicit failure, pipeline not started."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x
        from app.core.engine import ColmapEngine

        output = tmp_path / "output"
        images_dir = output / "proj" / "images"
        images_dir.mkdir(parents=True)  # empty

        engine = ColmapEngine(
            MagicMock(), str(images_dir), str(output),
            "images", 5, project_name="proj", logger_callback=print
        )
        engine.project_root = tmp_path
        engine.resume_colmap = True

        with patch.object(engine, "_run_reconstruction_pipeline") as mock_pipeline:
            ok, _msg = engine.run()

        assert ok is False
        mock_pipeline.assert_not_called()

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.is_apple_silicon")
    def test_validate_project_name_with_dots_blocked(self, mock_silicon, mock_resolve_binary, tmp_path):
        """Project name with '..' → None."""
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
    @patch("app.core.engine.is_apple_silicon")
    def test_create_brush_config(self, mock_silicon, mock_resolve_binary, tmp_path):
        """create_brush_config generates the JSON file."""
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
# _run_upscale resume after a partial failure (F-003)
# ─────────────────────────────────────────────────────────────────────────────

class TestRunUpscaleResume:
    """F-003: an upscale that failed after the originals were moved to images_src
    must be relaunched on the next run, not silently skipped because images_src
    already exists. A completed upscale (sentinel present) must stay skipped."""

    def _make_engine(self, tmp_path):
        from app.core.engine import ColmapEngine
        engine = ColmapEngine(
            MagicMock(), str(tmp_path / "input"), str(tmp_path / "output"),
            "images", 5, project_name="proj", logger_callback=print
        )
        engine.upscale_config = {
            "active": True, "model_id": "realesrgan-x4plus", "scale": 4,
            "format": "png", "tile": 0, "tta": False, "compression": 0,
        }
        return engine

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.is_apple_silicon")
    def test_run_upscale_relaunches_after_partial_failure(self, mock_silicon, mock_resolve_binary, tmp_path):
        """images_src present without the completion sentinel → upscale is relaunched.

        Reproduces the F-003 flow: the first run moved the originals to images_src
        and failed; the user re-runs, _prepare_images refills images_dir with
        original-resolution files, and _run_upscale must re-upscale them instead
        of returning True silently."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        engine = self._make_engine(tmp_path)
        project_dir = tmp_path / "output" / "proj"
        images_dir = project_dir / "images"
        images_dir.mkdir(parents=True)
        (images_dir / "img_0001.png").write_bytes(b"original")
        # Left over from the failed first run: originals moved, no sentinel.
        images_src = project_dir / "images_src"
        images_src.mkdir(parents=True)
        (images_src / "img_0001.png").write_bytes(b"original")

        with patch("app.core.upscale_engine.UpscaleEngine.is_installed", return_value=True):
            with patch("app.core.upscale_engine.UpscaleEngine.upscale_folder",
                       return_value=(True, "ok")) as mock_upscale:
                result = engine._run_upscale(project_dir, images_dir)

        assert result is True
        mock_upscale.assert_called_once()
        assert (images_src / ".upscale_complete").exists()

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.is_apple_silicon")
    def test_run_upscale_reports_failure_instead_of_silent_skip(self, mock_silicon, mock_resolve_binary, tmp_path):
        """images_src present without the sentinel and a failing upscaler → the
        failure is signalled, not swallowed by the resume branch."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        engine = self._make_engine(tmp_path)
        project_dir = tmp_path / "output" / "proj"
        images_dir = project_dir / "images"
        images_dir.mkdir(parents=True)
        (images_dir / "img_0001.png").write_bytes(b"original")
        images_src = project_dir / "images_src"
        images_src.mkdir(parents=True)
        (images_src / "img_0001.png").write_bytes(b"original")

        with patch("app.core.upscale_engine.UpscaleEngine.is_installed", return_value=True):
            with patch("app.core.upscale_engine.UpscaleEngine.upscale_folder",
                       return_value=(False, "boom")) as mock_upscale:
                result = engine._run_upscale(project_dir, images_dir)

        assert result is False
        mock_upscale.assert_called_once()
        assert not (images_src / ".upscale_complete").exists()

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.is_apple_silicon")
    def test_run_upscale_skips_when_completed(self, mock_silicon, mock_resolve_binary, tmp_path):
        """Legitimate resume: images_src present with the sentinel and images_dir
        holding the upscaled outputs → upscale is NOT relaunched."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        engine = self._make_engine(tmp_path)
        project_dir = tmp_path / "output" / "proj"
        images_dir = project_dir / "images"
        images_dir.mkdir(parents=True)
        (images_dir / "img_0001.png").write_bytes(b"upscaled")
        images_src = project_dir / "images_src"
        images_src.mkdir(parents=True)
        (images_src / "img_0001.png").write_bytes(b"original")
        (images_src / ".upscale_complete").write_text("ok", encoding="utf-8")

        with patch("app.core.upscale_engine.UpscaleEngine.is_installed", return_value=True):
            with patch("app.core.upscale_engine.UpscaleEngine.upscale_folder",
                       return_value=(True, "ok")) as mock_upscale:
                result = engine._run_upscale(project_dir, images_dir)

        assert result is True
        mock_upscale.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Blur filtering selection logic
# ─────────────────────────────────────────────────────────────────────────────

class TestSelectBlurryFiles:
    """Tests for engine.select_blurry_files()."""

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


# ─────────────────────────────────────────────────────────────────────────────
# ALIKED / LightGlue integration tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAlikedLightGlue:
    """Tests for the ALIKED features and LightGlue matching."""

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.is_apple_silicon")
    def test_feature_extraction_aliked(self, mock_silicon, mock_resolve_binary, tmp_path):
        """ALIKED feature_extraction uses --FeatureExtraction.type and --AlikedExtraction.*."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        from app.core.engine import ColmapEngine

        params = MagicMock()
        params.camera_model = "SIMPLE_RADIAL"
        params.single_camera = True
        params.max_image_size = 3200
        params.max_num_features = 8192
        params.feature_type = "ALIKED_N16ROT"
        params.matching_type = "ALIKED_BRUTEFORCE"
        params.estimate_affine_shape = False
        params.domain_size_pooling = False
        params.matcher_type = "exhaustive"

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
                assert "--FeatureExtraction.type" in cmd
                assert "ALIKED_N16ROT" in cmd
                assert "--AlikedExtraction.max_num_features" in cmd
                assert "--SiftExtraction.max_num_features" not in cmd
                assert "--SiftExtraction.estimate_affine_shape" not in cmd

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.is_apple_silicon")
    def test_feature_extraction_sift_preserved(self, mock_silicon, mock_resolve_binary, tmp_path):
        """SIFT stays the default and uses the SiftExtraction.* flags."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        from app.core.engine import ColmapEngine

        params = MagicMock()
        params.camera_model = "SIMPLE_RADIAL"
        params.single_camera = True
        params.max_image_size = 3200
        params.max_num_features = 8192
        params.feature_type = "SIFT"
        params.matching_type = "SIFT_BRUTEFORCE"
        params.estimate_affine_shape = True
        params.domain_size_pooling = True
        params.matcher_type = "exhaustive"

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
                assert "--FeatureExtraction.type" in cmd
                assert "SIFT" in cmd
                assert "--SiftExtraction.max_num_features" in cmd
                assert "--SiftExtraction.estimate_affine_shape" in cmd
                assert "--SiftExtraction.domain_size_pooling" in cmd
                assert "--AlikedExtraction.max_num_features" not in cmd

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.is_apple_silicon")
    def test_matching_aliked_lightglue(self, mock_silicon, mock_resolve_binary, tmp_path):
        """ALIKED + LightGlue combined match."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        from app.core.engine import ColmapEngine

        params = MagicMock()
        params.matching_type = "ALIKED_LIGHTGLUE"
        params.feature_type = "ALIKED_N16ROT"
        params.matcher_type = "exhaustive"
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
            assert "--FeatureMatching.type" in cmd
            assert "ALIKED_LIGHTGLUE" in cmd
            # LightGlue does not take the SiftMatching.* flags
            assert "--SiftMatching.max_ratio" not in cmd

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.is_apple_silicon")
    def test_matching_aliked_bruteforce_min_cossim(self, mock_silicon, mock_resolve_binary, tmp_path):
        """ALIKED + bruteforce ajoute --AlikedMatching.min_cossim."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        from app.core.engine import ColmapEngine

        params = MagicMock()
        params.matching_type = "ALIKED_BRUTEFORCE"
        params.feature_type = "ALIKED_N32"
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
            assert "--FeatureMatching.type" in cmd
            assert "ALIKED_BRUTEFORCE" in cmd
            assert "--AlikedMatching.min_cossim" in cmd

    @patch("app.core.engine.resolve_binary")
    @patch("app.core.engine.is_apple_silicon")
    def test_matching_sift_lightglue(self, mock_silicon, mock_resolve_binary, tmp_path):
        """SIFT + LightGlue is supported."""
        mock_silicon.return_value = False
        mock_resolve_binary.side_effect = lambda x: x

        from app.core.engine import ColmapEngine

        params = MagicMock()
        params.matching_type = "SIFT_LIGHTGLUE"
        params.feature_type = "SIFT"
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
            assert "--FeatureMatching.type" in cmd
            assert "SIFT_LIGHTGLUE" in cmd
            # SIFT + LightGlue: no SiftMatching.* flags
            assert "--SiftMatching.max_ratio" not in cmd


# ─────────────────────────────────────────────────────────────────────────────
# Tests for app/cli/commands.py — _resolve_matching_type
# ─────────────────────────────────────────────────────────────────────────────

class TestResolveMatchingType:
    """Tests for _resolve_matching_type()."""

    def test_explicit_match_type_is_returned(self):
        from app.cli.commands import _resolve_matching_type
        assert _resolve_matching_type("SIFT", "SIFT_LIGHTGLUE") == "SIFT_LIGHTGLUE"
        assert _resolve_matching_type("ALIKED_N16ROT", "ALIKED_LIGHTGLUE") == "ALIKED_LIGHTGLUE"

    def test_default_for_sift(self):
        from app.cli.commands import _resolve_matching_type
        assert _resolve_matching_type("SIFT", None) == "SIFT_BRUTEFORCE"

    def test_default_for_aliked(self):
        # ALIKED features default to LightGlue matching (ALIKED/LightGlue integration)
        from app.cli.commands import _resolve_matching_type
        assert _resolve_matching_type("ALIKED_N16ROT", None) == "ALIKED_LIGHTGLUE"
        assert _resolve_matching_type("ALIKED_N32", None) == "ALIKED_LIGHTGLUE"

    def test_unknown_feature_type_falls_back(self):
        from app.cli.commands import _resolve_matching_type
        assert _resolve_matching_type("UNKNOWN_FEATURE", None) == "SIFT_BRUTEFORCE"
