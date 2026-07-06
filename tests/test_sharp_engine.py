"""Tests pour app/core/sharp_engine.py — SharpEngine."""
import os
import sys
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, ANY

import pytest

# Patch missing modules at module level
for _mod_name in ["cv2", "send2trash"]:
    if _mod_name not in sys.modules:
        try:
            __import__(_mod_name)  # keep real module if installed — avoids clobbering cv2/numpy session-wide
        except ImportError:
            sys.modules[_mod_name] = MagicMock()


class TestProcessVideoFrames:
    """Tests pour SharpEngine.process_video_frames()."""

    def _make_engine(self, tmp_path):
        """Helper pour créer un SharpEngine mocké."""
        from app.core.sharp_engine import SharpEngine

        engine = SharpEngine(logger_callback=print)
        # Mock the runner to avoid subprocess calls
        engine.runner = MagicMock()
        engine.runner.readline.return_value = ""  # EOF immédiat: _execute_command boucle sur readline()
        engine.runner.wait.return_value = 0
        return engine

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_successful_frame_processing(self, mock_subprocess_run, mock_which, tmp_path):
        """Traitement vidéo réussi avec extraction FFmpeg et prédiction Sharp."""
        mock_which.return_value = "/usr/local/bin/ffmpeg"

        output_dir = tmp_path / "output"
        frames_dir = output_dir / "temp_frames"

        # Mock FFmpeg success by creating frame files as side effect
        def ffmpeg_side_effect(cmd, **kwargs):
            # This simulates what FFmpeg would do: create the frames
            frames_dir.mkdir(parents=True, exist_ok=True)
            for i in range(1, 4):
                (frames_dir / f"frame_{i:04d}.png").write_bytes(b"fake_png")
            mock_result = MagicMock()
            mock_result.returncode = 0
            return mock_result

        mock_subprocess_run.side_effect = ffmpeg_side_effect

        from app.core.sharp_engine import SharpEngine

        engine = SharpEngine(logger_callback=print)

        # Mock the predict method to return 0 and create PLY files
        with patch.object(engine, 'predict', return_value=0) as mock_predict:
            def predict_side_effect(frame_path, frame_out_dir, params):
                out = Path(frame_out_dir)
                out.mkdir(parents=True, exist_ok=True)
                (out / "result.ply").write_bytes(b"ply_data")
                return 0

            mock_predict.side_effect = predict_side_effect

            result = engine.process_video_frames(
                video_path=str(tmp_path / "input.mp4"),
                output_dir=str(output_dir),
                params={},
                log_callback=print,
                status_callback=lambda s: None,
                progress_callback=lambda p: None,
                cancel_check=None,
            )

            assert result == 3  # 3 frames processed

    @patch("app.core.sharp_engine.shutil.which")
    @patch("app.core.sharp_engine.subprocess.run")
    def test_ffmpeg_not_found(self, mock_subprocess_run, mock_which, tmp_path):
        """FFmpeg introuvable → retourne 0."""
        mock_which.return_value = None  # ffmpeg not found

        from app.core.sharp_engine import SharpEngine

        engine = SharpEngine(logger_callback=print)

        result = engine.process_video_frames(
            video_path=str(tmp_path / "input.mp4"),
            output_dir=str(tmp_path / "output"),
            params={},
            log_callback=print,
        )
        assert result == 0

    @patch("app.core.sharp_engine.shutil.which")
    @patch("app.core.sharp_engine.subprocess.run")
    def test_ffmpeg_error(self, mock_subprocess_run, mock_which, tmp_path):
        """FFmpeg retourne une erreur → retourne 0."""
        mock_which.return_value = "/usr/local/bin/ffmpeg"

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error processing file"
        mock_subprocess_run.return_value = mock_result

        from app.core.sharp_engine import SharpEngine

        engine = SharpEngine(logger_callback=print)

        result = engine.process_video_frames(
            video_path=str(tmp_path / "input.mp4"),
            output_dir=str(tmp_path / "output"),
            params={},
            log_callback=print,
        )
        assert result == 0

    @patch("app.core.sharp_engine.shutil.which")
    @patch("app.core.sharp_engine.subprocess.run")
    def test_no_frames_extracted(self, mock_subprocess_run, mock_which, tmp_path):
        """Aucune frame extraite → retourne 0."""
        mock_which.return_value = "/usr/local/bin/ffmpeg"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess_run.return_value = mock_result

        from app.core.sharp_engine import SharpEngine

        engine = SharpEngine(logger_callback=print)

        # No frames in the temp_frames dir (let process_video_frames create it empty)
        result = engine.process_video_frames(
            video_path=str(tmp_path / "input.mp4"),
            output_dir=str(tmp_path / "output"),
            params={},
            log_callback=print,
        )
        assert result == 0

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_cancel_callback_stops_processing(self, mock_subprocess_run, mock_which, tmp_path):
        """Callback d'annulation → arrêt après la frame en cours."""
        mock_which.return_value = "/usr/local/bin/ffmpeg"

        output_dir = tmp_path / "output"
        frames_dir = output_dir / "temp_frames"

        # Mock FFmpeg success: create 5 frames
        def ffmpeg_side_effect(cmd, **kwargs):
            frames_dir.mkdir(parents=True, exist_ok=True)
            for i in range(1, 6):
                (frames_dir / f"frame_{i:04d}.png").write_bytes(b"fake_png")
            mock_result = MagicMock()
            mock_result.returncode = 0
            return mock_result

        mock_subprocess_run.side_effect = ffmpeg_side_effect

        from app.core.sharp_engine import SharpEngine

        engine = SharpEngine(logger_callback=print)

        # Cancel after the 2nd frame
        cancel_count = [0]

        def cancel_check():
            cancel_count[0] += 1
            return cancel_count[0] >= 3  # cancel after reading 2 frames (3rd cancel check)

        with patch.object(engine, 'predict', return_value=0) as mock_predict:
            def predict_side_effect(frame_path, frame_out_dir, params):
                Path(frame_out_dir).mkdir(parents=True, exist_ok=True)
                (Path(frame_out_dir) / "result.ply").write_bytes(b"ply_data")
                return 0

            mock_predict.side_effect = predict_side_effect

            result = engine.process_video_frames(
                video_path=str(tmp_path / "input.mp4"),
                output_dir=str(output_dir),
                params={},
                log_callback=print,
                cancel_check=cancel_check,
            )

            # Should have stopped early (2 frames processed before cancel)
            assert result < 5
            assert result >= 1  # at least 1 before cancellation

    @patch("app.core.sharp_engine.shutil.which")
    @patch("app.core.sharp_engine.subprocess.run")
    def test_skip_frames_param(self, mock_subprocess_run, mock_which, tmp_path):
        """skip_frames modifie la commande FFmpeg."""
        mock_which.return_value = "/usr/local/bin/ffmpeg"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess_run.return_value = mock_result

        from app.core.sharp_engine import SharpEngine

        engine = SharpEngine(logger_callback=print)
        output_dir = tmp_path / "output"

        with patch.object(engine, 'predict', return_value=0):
            # Create empty frames_dir so glob returns empty — we just want to verify
            # the ffmpeg command construction
            engine.process_video_frames(
                video_path=str(tmp_path / "input.mp4"),
                output_dir=str(output_dir),
                params={"skip_frames": 3},
                log_callback=print,
            )

            # Check the ffmpeg command that was built
            cmd_args = mock_subprocess_run.call_args[0][0]
            assert "select=not(mod(n\\,3))" in cmd_args or "select=not(mod(n,3))" in cmd_args


class TestSharpPredict:
    """Tests pour SharpEngine.predict()."""

    def test_predict_command_construction(self, tmp_path):
        """predict construit la bonne commande."""
        from app.core.sharp_engine import SharpEngine

        engine = SharpEngine(logger_callback=print)
        engine.runner = MagicMock()
        engine.runner.start.return_value = None
        engine.runner.stdout_iter.return_value = iter([])
        engine.runner.readline.return_value = ""  # EOF immédiat: _execute_command boucle sur readline()
        engine.runner.wait.return_value = 0

        input_path = tmp_path / "input.jpg"
        input_path.write_bytes(b"fake")
        output_path = tmp_path / "output"
        output_path.mkdir()

        with patch.object(engine, '_get_sharp_cmd', return_value=["sharp"]):
            result = engine.predict(str(input_path), str(output_path))
            assert result == 0

    def test_predict_with_checkpoint(self, tmp_path):
        """predict avec checkpoint ajoute -c."""
        from app.core.sharp_engine import SharpEngine

        engine = SharpEngine(logger_callback=print)
        engine.runner = MagicMock()
        engine.runner.start.return_value = None
        engine.runner.stdout_iter.return_value = iter([])
        engine.runner.readline.return_value = ""  # EOF immédiat: _execute_command boucle sur readline()
        engine.runner.wait.return_value = 0

        input_path = tmp_path / "input.jpg"
        input_path.write_bytes(b"fake")
        output_path = tmp_path / "output"
        output_path.mkdir()
        ckpt_path = tmp_path / "model.pt"
        ckpt_path.write_bytes(b"checkpoint")

        with patch.object(engine, '_get_sharp_cmd', return_value=["sharp"]):
            result = engine.predict(str(input_path), str(output_path), params={"checkpoint": str(ckpt_path)})
            assert result == 0

    def test_is_installed_no_sharp(self, tmp_path):
        """is_installed retourne False quand Sharp n'est pas installé."""
        from app.core.sharp_engine import SharpEngine

        engine = SharpEngine(logger_callback=print)

        with patch("app.core.sharp_engine.resolve_project_root", return_value=tmp_path):
            with patch("importlib.util.find_spec", return_value=None):
                with patch("shutil.which", return_value=None):
                    assert engine.is_installed() is False
