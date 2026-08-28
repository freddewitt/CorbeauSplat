"""Tests pour app/core/four_dgs_engine.py — FourDGSEngine."""
import sys
from unittest.mock import MagicMock, patch

# ─────────────────────────────────────────────────────────────────────────────
# Tests for module-level functions
# ─────────────────────────────────────────────────────────────────────────────

class TestModuleFunctions:
    """Tests pour les fonctions module-level de four_dgs_engine.py."""

    def test_get_venv_4dgs_python(self):
        """get_venv_4dgs_python retourne un chemin finissant par .venv_4dgs/bin/python."""
        from app.core.four_dgs_engine import get_venv_4dgs_python
        with patch.object(sys, "platform", "darwin"):
            result = get_venv_4dgs_python()
            assert str(result).endswith(".venv_4dgs/bin/python")

    def test_get_venv_4dgs_python_windows(self):
        """get_venv_4dgs_python sur Windows retourne .venv_4dgs/Scripts/python.exe."""
        from app.core.four_dgs_engine import get_venv_4dgs_python
        with patch.object(sys, "platform", "win32"):
            result = get_venv_4dgs_python()
            assert str(result).endswith(".venv_4dgs\\Scripts\\python.exe") or str(result).endswith(".venv_4dgs/Scripts/python.exe")

    def test_get_ns_process_data_path(self):
        """_get_ns_process_data_path retourne un chemin finissant par .venv_4dgs/bin/ns-process-data."""
        from app.core.four_dgs_engine import _get_ns_process_data_path
        with patch.object(sys, "platform", "darwin"):
            result = _get_ns_process_data_path()
            assert str(result).endswith(".venv_4dgs/bin/ns-process-data")

    def test_get_ns_process_data_path_windows(self):
        """_get_ns_process_data_path sur Windows."""
        from app.core.four_dgs_engine import _get_ns_process_data_path
        with patch.object(sys, "platform", "win32"):
            result = _get_ns_process_data_path()
            assert str(result).endswith(".venv_4dgs\\Scripts\\ns-process-data.exe") or str(result).endswith(".venv_4dgs/Scripts/ns-process-data.exe")


# ─────────────────────────────────────────────────────────────────────────────
# Tests for FourDGSEngine
# ─────────────────────────────────────────────────────────────────────────────

class TestFourDGSEngine:
    """Tests pour la classe FourDGSEngine."""

    def test_init(self, tmp_path):
        """Initialisation du moteur 4DGS."""
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)
                assert engine.name == "4DGS"
                assert engine.ffmpeg == "ffmpeg"
                assert engine.colmap == "colmap"

    def test_check_nerfstudio_installed(self, tmp_path):
        """check_nerfstudio retourne True si ns-process-data existe."""
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
        """check_nerfstudio retourne False si ns-process-data n'existe pas."""
        from app.core.four_dgs_engine import FourDGSEngine

        engine = FourDGSEngine.__new__(FourDGSEngine)
        venv_bin = tmp_path / ".venv_4dgs" / "bin"
        engine.ns_process_data = str(venv_bin / "ns-process-data")

        with patch("app.core.four_dgs_engine._get_ns_process_data_path", return_value=venv_bin / "ns-process-data"):
            result = engine.check_nerfstudio()
            assert result is False

    def test_extract_frames(self, tmp_path):
        """extract_frames exécute FFmpeg via _execute_command."""
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)
                engine.runner = MagicMock()
                engine.runner.start.return_value = None
                engine.runner.stdout_iter.return_value = iter([])
                engine.runner.readline.return_value = ""  # EOF immédiat: _execute_command boucle sur readline()
                engine.runner.wait.return_value = 0

                video_path = tmp_path / "video.mp4"
                video_path.write_bytes(b"fake_video")
                output_dir = tmp_path / "frames"

                result = engine.extract_frames(str(video_path), str(output_dir), fps=5)
                assert result is True
                assert output_dir.exists()

    def test_extract_frames_apple_silicon(self, tmp_path):
        """extract_frames ajoute -hwaccel videotoolbox sur Apple Silicon."""
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x
                with patch("app.core.four_dgs_engine.is_apple_silicon", return_value=True):

                    from app.core.four_dgs_engine import FourDGSEngine

                    engine = FourDGSEngine(logger_callback=print)
                    engine.runner = MagicMock()
                    engine.runner.start.return_value = None
                    engine.runner.stdout_iter.return_value = iter([])
                    engine.runner.readline.return_value = ""  # EOF immédiat: _execute_command boucle sur readline()
                    engine.runner.wait.return_value = 0

                    video_path = tmp_path / "video.mp4"
                    video_path.write_bytes(b"fake")
                    output_dir = tmp_path / "frames"

                    result = engine.extract_frames(str(video_path), str(output_dir), fps=5)
                    assert result is True

    def test_extract_frames_stop_requested(self, tmp_path):
        """extract_frames retourne False si stop_requested."""
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)
                engine.stop_requested = True

                result = engine.extract_frames("/in", "/out", fps=5)
                assert result is False

    def test_run_colmap(self, tmp_path):
        """run_colmap exécute le pipeline COLMAP."""
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)
                engine.runner = MagicMock()
                engine.runner.start.return_value = None
                engine.runner.stdout_iter.return_value = iter([])
                engine.runner.readline.return_value = ""  # EOF immédiat: _execute_command boucle sur readline()
                engine.runner.wait.return_value = 0

                dataset_root = tmp_path / "dataset"
                dataset_root.mkdir()
                (dataset_root / "images").mkdir()

                result = engine.run_colmap(str(dataset_root))
                assert result is True

    def test_run_colmap_failure(self, tmp_path):
        """run_colmap en échec."""
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)
                engine.runner = MagicMock()
                engine.runner.start.return_value = None
                engine.runner.stdout_iter.return_value = iter([])
                engine.runner.readline.return_value = ""  # EOF immédiat: _execute_command boucle sur readline()
                engine.runner.wait.return_value = 1  # non-zero return code

                dataset_root = tmp_path / "dataset"
                dataset_root.mkdir()
                (dataset_root / "images").mkdir()

                result = engine.run_colmap(str(dataset_root))
                assert result is False

    def test_process_dataset_no_videos(self, tmp_path):
        """process_dataset sans vidéos → False."""
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
        """process_dataset avec vidéos et nerfstudio."""
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)
                engine.runner = MagicMock()
                engine.runner.start.return_value = None
                engine.runner.stdout_iter.return_value = iter([])
                engine.runner.readline.return_value = ""  # EOF immédiat: _execute_command boucle sur readline()
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
        """process_dataset sans nerfstudio → mode dégradé COLMAP."""
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)
                engine.runner = MagicMock()
                engine.runner.start.return_value = None
                engine.runner.stdout_iter.return_value = iter([])
                engine.runner.readline.return_value = ""  # EOF immédiat: _execute_command boucle sur readline()
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
                engine.runner.readline.return_value = ""  # EOF immédiat: _execute_command boucle sur readline()
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
        """upscale_config absent/inactif → aucune tentative d'upscale."""
        with patch("app.core.four_dgs_engine.resolve_project_root", return_value=tmp_path):
            with patch("app.core.four_dgs_engine.resolve_binary") as mock_resolve:
                mock_resolve.side_effect = lambda x: x

                from app.core.four_dgs_engine import FourDGSEngine

                engine = FourDGSEngine(logger_callback=print)
                assert engine.upscale_dataset_images(str(tmp_path)) is True

    def test_upscale_dataset_images_upscales_each_camera_folder(self, tmp_path):
        """upscale_config actif → chaque sous-dossier cam_XX est upscalé via UpscaleEngine."""
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
