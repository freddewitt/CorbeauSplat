"""Tests for app/core/four_dgs_engine.py — FourDGSEngine.
"""
import sys
from unittest.mock import MagicMock, patch

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Tests for module-level functions
# ─────────────────────────────────────────────────────────────────────────────

class TestModuleFunctions:
    """Tests for the module-level functions of four_dgs_engine.py."""

    def test_get_venv_4dgs_python(self):
        """get_venv_4dgs_python returns a path ending with .venv_4dgs/bin/python."""
        from app.core.four_dgs_engine import get_venv_4dgs_python
        with patch.object(sys, "platform", "darwin"):
            result = get_venv_4dgs_python()
            assert str(result).endswith(".venv_4dgs/bin/python")

    def test_get_venv_4dgs_python_windows(self):
        """get_venv_4dgs_python on Windows returns .venv_4dgs/Scripts/python.exe."""
        from app.core.four_dgs_engine import get_venv_4dgs_python
        with patch.object(sys, "platform", "win32"):
            result = get_venv_4dgs_python()
            assert str(result).endswith(".venv_4dgs\\Scripts\\python.exe") or str(result).endswith(".venv_4dgs/Scripts/python.exe")

    def test_get_ns_process_data_path(self):
        """_get_ns_process_data_path returns a path ending with .venv_4dgs/bin/ns-process-data."""
        from app.core.four_dgs_engine import _get_ns_process_data_path
        with patch.object(sys, "platform", "darwin"):
            result = _get_ns_process_data_path()
            assert str(result).endswith(".venv_4dgs/bin/ns-process-data")

    def test_get_ns_process_data_path_windows(self):
        """_get_ns_process_data_path on Windows."""
        from app.core.four_dgs_engine import _get_ns_process_data_path
        with patch.object(sys, "platform", "win32"):
            result = _get_ns_process_data_path()
            assert str(result).endswith(".venv_4dgs\\Scripts\\ns-process-data.exe") or str(result).endswith(".venv_4dgs/Scripts/ns-process-data.exe")


# ─────────────────────────────────────────────────────────────────────────────
# Tests for FourDGSEngine
# ─────────────────────────────────────────────────────────────────────────────

class TestFourDGSEngine:
    """Tests for the FourDGSEngine class."""

    def test_init(self, tmp_path):
        """Initialisation of the 4DGS engine."""
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)
                assert engine.name == "4DGS"
                assert engine.ffmpeg == "ffmpeg"
                assert engine.colmap == "colmap"

    def test_check_nerfstudio_installed(self, tmp_path):
        """check_nerfstudio returns True when ns-process-data exists."""
        from app.core.four_dgs_engine import FourDGSEngine

        engine = FourDGSEngine.__new__(FourDGSEngine)

        # Manually set the ns_process_data path
        venv_bin = tmp_path / ".venv_4dgs" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "ns-process-data").write_text("binary")
        engine.ns_process_data = str(venv_bin / "ns-process-data")

        with patch("app.core.four_dgs_engine._get_ns_process_data_path", return_value=venv_bin / "ns-process-data"):
            result = engine.check_nerfstudio()
            assert result is True

    def test_check_nerfstudio_not_installed(self, tmp_path):
        """check_nerfstudio returns False when ns-process-data does not exist."""
        from app.core.four_dgs_engine import FourDGSEngine

        engine = FourDGSEngine.__new__(FourDGSEngine)
        venv_bin = tmp_path / ".venv_4dgs" / "bin"
        engine.ns_process_data = str(venv_bin / "ns-process-data")

        with patch("app.core.four_dgs_engine._get_ns_process_data_path", return_value=venv_bin / "ns-process-data"):
            result = engine.check_nerfstudio()
            assert result is False

    def test_extract_frames(self, tmp_path):
        """extract_frames runs FFmpeg through _execute_command."""
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)
                engine.runner = MagicMock()
                engine.runner.start.return_value = None
                engine.runner.stdout_iter.return_value = iter([])
                engine.runner.readline.return_value = ""  # Immediate EOF: _execute_command loops on readline()
                engine.runner.wait.return_value = 0

                video_path = tmp_path / "video.mp4"
                video_path.write_bytes(b"fake_video")
                output_dir = tmp_path / "frames"

                result = engine.extract_frames(str(video_path), str(output_dir), fps=5)
                assert result is True
                assert output_dir.exists()

    def test_extract_frames_apple_silicon(self, tmp_path):
        """extract_frames adds -hwaccel videotoolbox on Apple Silicon."""
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x
                with patch("app.core.four_dgs_engine.is_apple_silicon", return_value=True):

                    from app.core.four_dgs_engine import FourDGSEngine

                    engine = FourDGSEngine(logger_callback=print)
                    engine.runner = MagicMock()
                    engine.runner.start.return_value = None
                    engine.runner.stdout_iter.return_value = iter([])
                    engine.runner.readline.return_value = ""  # Immediate EOF: _execute_command loops on readline()
                    engine.runner.wait.return_value = 0

                    video_path = tmp_path / "video.mp4"
                    video_path.write_bytes(b"fake")
                    output_dir = tmp_path / "frames"

                    result = engine.extract_frames(str(video_path), str(output_dir), fps=5)
                    assert result is True

    def test_extract_frames_stop_requested(self, tmp_path):
        """extract_frames returns False once stop_requested is set."""
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)
                engine.stop_requested = True

                result = engine.extract_frames("/in", "/out", fps=5)
                assert result is False

    def test_run_colmap(self, tmp_path):
        """run_colmap runs the COLMAP pipeline."""
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)
                engine.runner = MagicMock()
                engine.runner.start.return_value = None
                engine.runner.stdout_iter.return_value = iter([])
                engine.runner.readline.return_value = ""  # Immediate EOF: _execute_command loops on readline()
                engine.runner.wait.return_value = 0

                dataset_root = tmp_path / "dataset"
                dataset_root.mkdir()
                (dataset_root / "images").mkdir()

                result = engine.run_colmap(str(dataset_root))
                assert result is True

    def test_run_colmap_failure(self, tmp_path):
        """run_colmap on failure."""
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)
                engine.runner = MagicMock()
                engine.runner.start.return_value = None
                engine.runner.stdout_iter.return_value = iter([])
                engine.runner.readline.return_value = ""  # Immediate EOF: _execute_command loops on readline()
                engine.runner.wait.return_value = 1  # non-zero return code

                dataset_root = tmp_path / "dataset"
                dataset_root.mkdir()
                (dataset_root / "images").mkdir()

                result = engine.run_colmap(str(dataset_root))
                assert result is False

    def test_run_colmap_refuses_unsigned_existing_dir(self, tmp_path):
        """F-011: run_colmap returns False (and destroys nothing) when the
        output holds a pre-existing unsigned colmap_reference_frames dir.
        """
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)
                engine.runner = MagicMock()
                engine.runner.start.return_value = None
                engine.runner.stdout_iter.return_value = iter([])
                engine.runner.readline.return_value = ""
                engine.runner.wait.return_value = 0

                dataset_root = tmp_path / "dataset"
                images_root = dataset_root / "images"
                cam_dir = images_root / "cam_00"
                cam_dir.mkdir(parents=True)
                (cam_dir / "00000.jpg").write_bytes(b"fake")

                staging = dataset_root / "colmap_reference_frames"
                staging.mkdir()
                user_file = staging / "mes_photos.txt"
                user_file.write_text("données utilisateur précieuses", encoding="utf-8")

                result = engine.run_colmap(str(dataset_root))
                assert result is False
                assert user_file.exists()

    def test_run_colmap_uses_single_reference_frame_per_camera(self, tmp_path):
        """run_colmap must run COLMAP on 1 frame/camera, not on every frame of
        every timestep (COLMAP assumes a static scene).
        """
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)
                engine.runner = MagicMock()
                engine.runner.start.return_value = None
                engine.runner.stdout_iter.return_value = iter([])
                engine.runner.readline.return_value = ""
                engine.runner.wait.return_value = 0

                dataset_root = tmp_path / "dataset"
                images_root = dataset_root / "images"
                for cam in ("cam_00", "cam_01"):
                    cam_dir = images_root / cam
                    cam_dir.mkdir(parents=True)
                    for i in range(3):
                        (cam_dir / f"{i:05d}.jpg").write_bytes(b"fake")
                # Upscale leftover, must not be treated as a third camera
                (images_root / "cam_00_src").mkdir(parents=True)
                (images_root / "cam_00_src" / "00000.jpg").write_bytes(b"fake")

                result = engine.run_colmap(str(dataset_root))
                assert result is True

                staging_dir = dataset_root / "colmap_reference_frames"
                staged = sorted(p.name for p in staging_dir.iterdir())
                assert staged == ["cam_00.jpg", "cam_01.jpg"]

                extract_cmd = engine.runner.start.call_args_list[0][0][0]
                mapper_cmd = engine.runner.start.call_args_list[2][0][0]
                assert str(staging_dir) in extract_cmd
                assert str(staging_dir) in mapper_cmd

    def test_run_colmap_flat_images_no_camera_subfolders(self, tmp_path):
        """Without cam_XX sub-folders (flat single-camera dataset): no staging,
        COLMAP runs directly on images/.
        """
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)
                engine.runner = MagicMock()
                engine.runner.start.return_value = None
                engine.runner.stdout_iter.return_value = iter([])
                engine.runner.readline.return_value = ""
                engine.runner.wait.return_value = 0

                dataset_root = tmp_path / "dataset"
                images_root = dataset_root / "images"
                images_root.mkdir(parents=True)
                (images_root / "00000.jpg").write_bytes(b"fake")

                result = engine.run_colmap(str(dataset_root))
                assert result is True
                assert not (dataset_root / "colmap_reference_frames").exists()

                extract_cmd = engine.runner.start.call_args_list[0][0][0]
                assert str(images_root) in extract_cmd

    def test_build_static_reference_set_preserves_unsigned_existing_dir(self, tmp_path):
        """F-011: a pre-existing unsigned colmap_reference_frames dir (user data)
        must not be deleted by _build_static_reference_set — the run must fail
        with a clear error instead of silently destroying it.
        """
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)

                images_root = tmp_path / "images"
                cam_dir = images_root / "cam_00"
                cam_dir.mkdir(parents=True)
                (cam_dir / "00000.jpg").write_bytes(b"fake")

                staging = tmp_path / "colmap_reference_frames"
                staging.mkdir()
                user_file = staging / "mes_photos.txt"
                user_file.write_text("données utilisateur précieuses", encoding="utf-8")

                with pytest.raises(RuntimeError):
                    engine._build_static_reference_set(images_root, staging)

                assert user_file.exists()
                assert (staging / "mes_photos.txt").read_text(encoding="utf-8") == "données utilisateur précieuses"

    def test_build_static_reference_set_refuses_unsigned_empty_dir(self, tmp_path):
        """F-011: even an empty pre-existing colmap_reference_frames dir without
        the ownership marker is preserved, not destroyed.
        """
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)

                images_root = tmp_path / "images"
                cam_dir = images_root / "cam_00"
                cam_dir.mkdir(parents=True)
                (cam_dir / "00000.jpg").write_bytes(b"fake")

                staging = tmp_path / "colmap_reference_frames"
                staging.mkdir()

                with pytest.raises(RuntimeError):
                    engine._build_static_reference_set(images_root, staging)

                assert staging.exists()
                assert not (staging / "cam_00.jpg").exists()

    def test_build_static_reference_set_refuses_symlink_dir(self, tmp_path):
        """F-011: a colmap_reference_frames symlink (even with a forged sibling
        marker) is never rmtree'd — the app never creates symlinks there, so any
        symlink is user data.
        """
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)

                images_root = tmp_path / "images"
                cam_dir = images_root / "cam_00"
                cam_dir.mkdir(parents=True)
                (cam_dir / "00000.jpg").write_bytes(b"fake")

                user_data = tmp_path / "user_data"
                user_data.mkdir()
                user_file = user_data / "important.txt"
                user_file.write_text("secret", encoding="utf-8")
                staging = tmp_path / "colmap_reference_frames"
                staging.symlink_to(user_data, target_is_directory=True)
                (tmp_path / "colmap_reference_frames.corbeausplat_owned").write_text("owned-by-corbeausplat")

                with pytest.raises(RuntimeError):
                    engine._build_static_reference_set(images_root, staging)

                assert user_file.exists()

    def test_build_static_reference_set_reuses_owned_dir(self, tmp_path):
        """F-011: a colmap_reference_frames dir created by a previous app run
        (ownership marker present) is replaced without error on the next run.
        """
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)

                images_root = tmp_path / "images"
                cam_dir = images_root / "cam_00"
                cam_dir.mkdir(parents=True)
                (cam_dir / "00000.jpg").write_bytes(b"fake")

                staging = tmp_path / "colmap_reference_frames"

                result = engine._build_static_reference_set(images_root, staging)
                assert result == staging
                marker = staging.parent / (staging.name + ".corbeausplat_owned")
                assert marker.exists()

                # Second run: the app-created dir is signed → replaced, no error.
                result2 = engine._build_static_reference_set(images_root, staging)
                assert result2 == staging
                assert (staging / "cam_00.jpg").exists()
                assert marker.exists()

    def test_process_dataset_no_videos(self, tmp_path):
        """process_dataset without videos → False."""
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)

                videos_dir = tmp_path / "videos"
                videos_dir.mkdir()
                output_dir = tmp_path / "output"

                result = engine.process_dataset(str(videos_dir), str(output_dir), fps=5)
                assert result is False

    def test_process_dataset_with_videos(self, tmp_path):
        """process_dataset with videos and nerfstudio."""
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)
                engine.runner = MagicMock()
                engine.runner.start.return_value = None
                engine.runner.stdout_iter.return_value = iter([])
                engine.runner.readline.return_value = ""  # Immediate EOF: _execute_command loops on readline()
                engine.runner.wait.return_value = 0

                # Create video files
                videos_dir = tmp_path / "videos"
                videos_dir.mkdir()
                (videos_dir / "cam01.mp4").write_bytes(b"fake_video")
                (videos_dir / "cam02.mp4").write_bytes(b"fake_video")
                output_dir = tmp_path / "output"

                # Mock check_nerfstudio to return True
                with patch.object(engine, 'check_nerfstudio', return_value=True):
                    result = engine.process_dataset(str(videos_dir), str(output_dir), fps=5)
                    assert result is True

    def test_process_dataset_no_nerfstudio(self, tmp_path):
        """process_dataset without nerfstudio → degraded COLMAP mode."""
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)
                engine.runner = MagicMock()
                engine.runner.start.return_value = None
                engine.runner.stdout_iter.return_value = iter([])
                engine.runner.readline.return_value = ""  # Immediate EOF: _execute_command loops on readline()
                engine.runner.wait.return_value = 0

                videos_dir = tmp_path / "videos"
                videos_dir.mkdir()
                (videos_dir / "cam01.mp4").write_bytes(b"fake")
                output_dir = tmp_path / "output"

                # Mock check_nerfstudio to return False
                with patch.object(engine, 'check_nerfstudio', return_value=False):
                    with patch.object(engine, 'run_colmap', return_value=True) as mock_colmap:
                        result = engine.process_dataset(str(videos_dir), str(output_dir), fps=5)
                        assert result is True
                        mock_colmap.assert_called_once_with(str(output_dir))

    def test_process_dataset_ignores_appledouble_files(self, tmp_path):
        """macOS AppleDouble files (._*) must not be treated as videos (crashes ffmpeg)."""
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)
                engine.runner = MagicMock()
                engine.runner.start.return_value = None
                engine.runner.stdout_iter.return_value = iter([])
                engine.runner.readline.return_value = ""  # Immediate EOF: _execute_command loops on readline()
                engine.runner.wait.return_value = 0

                videos_dir = tmp_path / "videos"
                videos_dir.mkdir()
                (videos_dir / "cam01.mp4").write_bytes(b"fake_video")
                (videos_dir / "._cam01.mp4").write_bytes(b"appledouble_metadata")
                output_dir = tmp_path / "output"

                with patch.object(engine, 'check_nerfstudio', return_value=False):
                    with patch.object(engine, 'extract_frames', return_value=True) as mock_extract:
                        with patch.object(engine, 'run_colmap', return_value=True):
                            result = engine.process_dataset(str(videos_dir), str(output_dir), fps=5)
                            assert result is True
                            assert mock_extract.call_count == 1
                            called_video_path = mock_extract.call_args[0][0]
                            assert called_video_path.name == "cam01.mp4"

    def test_upscale_dataset_images_inactive_is_noop(self, tmp_path):
        """upscale_config missing/inactive → no upscale attempt."""
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)
                assert engine.upscale_dataset_images(str(tmp_path)) is True

    def test_upscale_dataset_images_upscales_each_camera_folder(self, tmp_path):
        """upscale_config active → every cam_XX sub-folder is upscaled through UpscaleEngine."""
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)
                engine.upscale_config = {"active": True, "model_id": "realesrgan-x4plus", "scale": 4}

                output_dir = tmp_path / "output"
                images_root = output_dir / "images"
                (images_root / "cam_00").mkdir(parents=True)
                (images_root / "cam_01").mkdir(parents=True)

                with patch("app.core.upscale_engine.UpscaleEngine.is_installed", return_value=True):
                    with patch("app.core.upscale_engine.UpscaleEngine.upscale_folder",
                               return_value=(True, "ok")) as mock_upscale:
                        result = engine.upscale_dataset_images(str(output_dir))
                        assert result is True
                        assert mock_upscale.call_count == 2
                        assert (images_root / "cam_00_src").is_dir()
                        assert (images_root / "cam_01_src").is_dir()

    def test_upscale_dataset_images_relaunches_after_partial_failure(self, tmp_path):
        """F-003: a cam_XX_src folder without the completion sentinel is upscaled
        again on the next run instead of being skipped as 'already upscaled', and
        the completed cam_01 (sentinel present) stays skipped."""
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)
                engine.upscale_config = {"active": True, "model_id": "realesrgan-x4plus", "scale": 4}

                output_dir = tmp_path / "output"
                images_root = output_dir / "images"
                # cam_00: failed first run left cam_00_src without a sentinel.
                (images_root / "cam_00").mkdir(parents=True)
                (images_root / "cam_00").joinpath("frame_0000.png").write_bytes(b"original")
                (images_root / "cam_00_src").mkdir(parents=True)
                (images_root / "cam_00_src").joinpath("frame_0000.png").write_bytes(b"original")
                # cam_01: completed with sentinel → must stay skipped.
                (images_root / "cam_01").mkdir(parents=True)
                (images_root / "cam_01").joinpath("frame_0000.png").write_bytes(b"upscaled")
                (images_root / "cam_01_src").mkdir(parents=True)
                (images_root / "cam_01_src").joinpath("frame_0000.png").write_bytes(b"original")
                (images_root / "cam_01_src" / ".upscale_complete").write_text("ok", encoding="utf-8")

                with patch("app.core.upscale_engine.UpscaleEngine.is_installed", return_value=True):
                    with patch("app.core.upscale_engine.UpscaleEngine.upscale_folder",
                               return_value=(True, "ok")) as mock_upscale:
                        result = engine.upscale_dataset_images(str(output_dir))

                assert result is True
                assert mock_upscale.call_count == 1
                assert mock_upscale.call_args.kwargs["input_dir"].endswith("cam_00_src")
                assert mock_upscale.call_args.kwargs["output_dir"].endswith("cam_00")
                assert (images_root / "cam_00_src" / ".upscale_complete").exists()
