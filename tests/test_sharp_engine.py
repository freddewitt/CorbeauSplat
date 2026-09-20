"""Tests pour app/core/sharp_engine.py — SharpEngine."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Patch missing modules at module level
for _mod_name in ["cv2", "send2trash"]:
    if _mod_name not in sys.modules:
        try:
            __import__(_mod_name)  # keep real module if installed — avoids clobbering cv2/numpy session-wide
        except ImportError:
            sys.modules[_mod_name] = MagicMock()


class TestProcessVideoFrames:
    """Tests for SharpEngine.process_video_frames()."""

    def _make_engine(self, tmp_path):
        """Build a mocked SharpEngine."""
        from app.core.sharp_engine import SharpEngine

        engine = SharpEngine(logger_callback=print)
        # Mock the runner to avoid subprocess calls
        engine.runner = MagicMock()
        engine.runner.readline.return_value = ""  # Immediate EOF: _execute_command loops on readline()
        engine.runner.wait.return_value = 0
        return engine

    def test_successful_frame_processing(self, tmp_path):
        """Successful video run: FFmpeg extraction then Sharp prediction."""
        output_dir = tmp_path / "output"
        frames_dir = output_dir / "temp_frames"

        from app.core.sharp_engine import SharpEngine

        engine = SharpEngine(logger_callback=print)
        engine.runner = MagicMock()

        # Mock FFmpeg success by creating frame files as side effect of start()
        def ffmpeg_side_effect(cmd, env=None, **kwargs):
            frames_dir.mkdir(parents=True, exist_ok=True)
            for i in range(1, 4):
                (frames_dir / f"frame_{i:04d}.png").write_bytes(b"fake_png")

        engine.runner.start.side_effect = ffmpeg_side_effect
        engine.runner.readline.return_value = ""  # Immediate EOF
        engine.runner.wait.return_value = 0

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

    def test_ffmpeg_not_found(self, tmp_path):
        """FFmpeg introuvable → retourne 0."""
        from app.core.sharp_engine import SharpEngine

        engine = SharpEngine(logger_callback=print)
        engine.runner = MagicMock()
        engine.runner.start.side_effect = FileNotFoundError("ffmpeg not found")

        result = engine.process_video_frames(
            video_path=str(tmp_path / "input.mp4"),
            output_dir=str(tmp_path / "output"),
            params={},
            log_callback=print,
        )
        assert result == 0

    def test_ffmpeg_error(self, tmp_path):
        """FFmpeg returns an error → returns 0."""
        from app.core.sharp_engine import SharpEngine

        engine = SharpEngine(logger_callback=print)
        engine.runner = MagicMock()
        engine.runner.readline.return_value = ""  # Immediate EOF
        engine.runner.wait.return_value = 1

        result = engine.process_video_frames(
            video_path=str(tmp_path / "input.mp4"),
            output_dir=str(tmp_path / "output"),
            params={},
            log_callback=print,
        )
        assert result == 0

    def test_no_frames_extracted(self, tmp_path):
        """No frame extracted → returns 0."""
        from app.core.sharp_engine import SharpEngine

        engine = SharpEngine(logger_callback=print)
        engine.runner = MagicMock()
        engine.runner.readline.return_value = ""  # Immediate EOF
        engine.runner.wait.return_value = 0

        # No frames in the temp_frames dir (let process_video_frames create it empty)
        result = engine.process_video_frames(
            video_path=str(tmp_path / "input.mp4"),
            output_dir=str(tmp_path / "output"),
            params={},
            log_callback=print,
        )
        assert result == 0

    def test_cancel_callback_stops_processing(self, tmp_path):
        """Cancel callback → stops after the frame in progress."""
        output_dir = tmp_path / "output"
        frames_dir = output_dir / "temp_frames"

        from app.core.sharp_engine import SharpEngine

        engine = SharpEngine(logger_callback=print)
        engine.runner = MagicMock()

        # Mock FFmpeg success: create 5 frames
        def ffmpeg_side_effect(cmd, env=None, **kwargs):
            frames_dir.mkdir(parents=True, exist_ok=True)
            for i in range(1, 6):
                (frames_dir / f"frame_{i:04d}.png").write_bytes(b"fake_png")

        engine.runner.start.side_effect = ffmpeg_side_effect
        engine.runner.readline.return_value = ""  # Immediate EOF
        engine.runner.wait.return_value = 0

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

    def test_skip_frames_param(self, tmp_path):
        """skip_frames modifie la commande FFmpeg."""
        from app.core.sharp_engine import SharpEngine

        engine = SharpEngine(logger_callback=print)
        engine.runner = MagicMock()
        engine.runner.readline.return_value = ""  # Immediate EOF
        engine.runner.wait.return_value = 0
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
            cmd_args = engine.runner.start.call_args[0][0]
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
        engine.runner.readline.return_value = ""  # Immediate EOF: _execute_command loops on readline()
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
        engine.runner.readline.return_value = ""  # Immediate EOF: _execute_command loops on readline()
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
        """is_installed returns False when Sharp is not installed."""
        from app.core.sharp_engine import SharpEngine

        engine = SharpEngine(logger_callback=print)

        with patch("app.core.sharp_engine.resolve_project_root", return_value=tmp_path):
            with patch("importlib.util.find_spec", return_value=None):
                with patch("shutil.which", return_value=None):
                    assert engine.is_installed() is False


class TestVideoRunSafety:
    """Cancellation, duration estimate and folder deletion (audit I14)."""

    def _engine_with_frames(self, tmp_path, frame_count=3):
        """SharpEngine whose fake FFmpeg drops `frame_count` images."""
        from app.core.sharp_engine import SharpEngine

        frames_dir = tmp_path / "output" / "temp_frames"

        def ffmpeg_side_effect(cmd, env=None, **kwargs):
            frames_dir.mkdir(parents=True, exist_ok=True)
            for i in range(1, frame_count + 1):
                (frames_dir / f"frame_{i:04d}.png").write_bytes(b"fake_png")

        engine = SharpEngine(logger_callback=print)
        engine.runner = MagicMock()
        engine.runner.start.side_effect = ffmpeg_side_effect
        engine.runner.readline.return_value = ""
        engine.runner.wait.return_value = 0
        return engine

    def test_stop_requested_interrupts_the_loop(self, tmp_path):
        """stop() interrupts the loop even without cancel_check.

        Regression: only cancel_check was covered, so stop() let the run
        walk through every remaining image.
        """
        engine = self._engine_with_frames(tmp_path, frame_count=3)

        with patch.object(engine, 'predict', return_value=0) as mock_predict:
            engine.stop_requested = True
            result = engine.process_video_frames(
                video_path=str(tmp_path / "input.mp4"),
                output_dir=str(tmp_path / "output"),
                params={},
                log_callback=print,
            )

        assert result == 0
        mock_predict.assert_not_called()

    def test_existing_user_folder_is_never_deleted(self, tmp_path):
        """A user folder named like a frame is neither overwritten nor deleted."""
        output_dir = tmp_path / "output"
        engine = self._engine_with_frames(tmp_path, frame_count=1)

        # Collides with the name derived from frame_0001.png.
        user_dir = output_dir / "frame_0001"
        user_dir.mkdir(parents=True)
        user_file = user_dir / "important.txt"
        user_file.write_text("do not touch")

        def predict_side_effect(frame_path, frame_out_dir, params):
            out = Path(frame_out_dir)
            out.mkdir(parents=True, exist_ok=True)
            (out / "result.ply").write_bytes(b"ply_data")
            return 0

        with patch.object(engine, 'predict', side_effect=predict_side_effect):
            engine.process_video_frames(
                video_path=str(tmp_path / "input.mp4"),
                output_dir=str(output_dir),
                params={},
                log_callback=print,
            )

        assert user_file.exists()
        assert user_file.read_text() == "do not touch"

    def test_long_run_confirmation_aborts_before_any_inference(self, tmp_path):
        """Declining the confirmation stops before any inference and purges the frames."""
        from app.core.sharp_engine import LONG_RUN_CONFIRM_SECONDS, SECONDS_PER_FRAME_ESTIMATE

        frame_count = int(LONG_RUN_CONFIRM_SECONDS / SECONDS_PER_FRAME_ESTIMATE) + 1
        engine = self._engine_with_frames(tmp_path, frame_count=frame_count)
        asked = []

        with patch.object(engine, 'predict', return_value=0) as mock_predict:
            result = engine.process_video_frames(
                video_path=str(tmp_path / "input.mp4"),
                output_dir=str(tmp_path / "output"),
                params={},
                log_callback=print,
                confirm_callback=lambda n, secs: asked.append((n, secs)) or False,
            )

        assert result == 0
        mock_predict.assert_not_called()
        assert asked and asked[0][0] == frame_count
        assert not (tmp_path / "output" / "temp_frames").exists()

    def test_short_run_is_not_confirmed(self, tmp_path):
        """Below the threshold, no confirmation is asked."""
        engine = self._engine_with_frames(tmp_path, frame_count=1)
        asked = []

        with patch.object(engine, 'predict', return_value=0):
            engine.process_video_frames(
                video_path=str(tmp_path / "input.mp4"),
                output_dir=str(tmp_path / "output"),
                params={},
                log_callback=print,
                confirm_callback=lambda n, secs: asked.append(n) or True,
            )

        assert asked == []
