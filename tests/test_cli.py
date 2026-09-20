"""Tests for app.cli — CLI dispatch and argparse parsing.
"""
import sys
from unittest.mock import MagicMock, patch

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Patching the missing modules BEFORE any project code import.
# app.cli.commands imports send2trash through engine.py and PySide6 through main_window.py.
# We patch sys.modules at module level to avoid ImportError.
# ─────────────────────────────────────────────────────────────────────────────
_missing_modules = {}
for _mod_name in ["send2trash", "PySide6", "PySide6.QtWidgets", "PySide6.QtGui",
                  "PySide6.QtCore", "AppKit", "cv2"]:
    if _mod_name not in sys.modules:
        try:
            # Keep the real module when installed (cv2/send2trash) — mocking it
            # unconditionally clobbers it session-wide and breaks other tests
            # (e.g. the COLMAP integration pipeline needs real cv2.imread).
            __import__(_mod_name)
        except ImportError:
            _missing_modules[_mod_name] = MagicMock()

# Patch PySide6.QtCore.Signal
if "PySide6.QtCore" in _missing_modules:
    _missing_modules["PySide6.QtCore"].Signal = MagicMock()
    _missing_modules["PySide6.QtCore"].QTimer = MagicMock()
    _missing_modules["PySide6.QtCore"].QThread = MagicMock()

for _mod, _mock in _missing_modules.items():
    sys.modules[_mod] = _mock


# ─────────────────────────────────────────────────────────────────────────────
# Parser tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCLIParser:
    """Unit tests of the argparse parsing."""

    def test_no_args_returns_none_command(self):
        """No argument → command=None, gui=False."""
        from app.cli.parser import get_parser
        parser = get_parser()
        args = parser.parse_args([])
        assert args.command is None
        assert args.gui is False

    def test_gui_flag(self):
        """--gui → gui=True."""
        from app.cli.parser import get_parser
        parser = get_parser()
        args = parser.parse_args(["--gui"])
        assert args.gui is True

    def test_pipeline_command(self):
        """pipeline sub-command with the mandatory arguments."""
        from app.cli.parser import get_parser
        parser = get_parser()
        args = parser.parse_args([
            "pipeline",
            "-i", "/input/video.mp4",
            "-o", "/output/dir",
        ])
        assert args.command == "pipeline"
        assert args.input == "/input/video.mp4"
        assert args.output == "/output/dir"
        assert args.type == "images"  # default
        assert args.fps == 5  # default

    def test_pipeline_with_all_options(self):
        """Pipeline with every option spelled out."""
        from app.cli.parser import get_parser
        parser = get_parser()
        args = parser.parse_args([
            "pipeline",
            "-i", "/in",
            "-o", "/out",
            "--project_name", "test_scene",
            "--type", "video",
            "--fps", "10",
            "--camera_model", "OPENCV",
            "--undistort",
            "--matcher_type", "sequential",
            "--preset", "dense",
            "--iterations", "50000",
            "--sh_degree", "3",
            "--device", "mps",
            "--with_viewer",
            "--ply_name", "result.ply",
        ])
        assert args.command == "pipeline"
        assert args.project_name == "test_scene"
        assert args.type == "video"
        assert args.fps == 10
        assert args.camera_model == "OPENCV"
        assert args.undistort is True
        assert args.matcher_type == "sequential"
        assert args.preset == "dense"
        assert args.iterations == 50000
        assert args.sh_degree == 3
        assert args.device == "mps"
        assert args.with_viewer is True
        assert args.ply_name == "result.ply"

    def test_colmap_mandatory_args(self):
        """colmap sub-command requires input and output."""
        from app.cli.parser import get_parser
        parser = get_parser()
        args = parser.parse_args(["colmap", "-i", "/in", "-o", "/out"])
        assert args.command == "colmap"
        assert args.input == "/in"
        assert args.output == "/out"

    def test_colmap_missing_input(self):
        """colmap without --input → SystemExit error."""
        from app.cli.parser import get_parser
        parser = get_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["colmap", "-o", "/out"])

    def test_colmap_missing_output(self):
        """colmap without --output → SystemExit error."""
        from app.cli.parser import get_parser
        parser = get_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["colmap", "-i", "/in"])

    def test_brush_command(self):
        """brush sub-command with the mandatory arguments."""
        from app.cli.parser import get_parser
        parser = get_parser()
        args = parser.parse_args([
            "brush",
            "-i", "/input",
            "-o", "/output",
            "--preset", "fast",
            "--iterations", "7000",
            "--device", "mps",
        ])
        assert args.command == "brush"
        assert args.preset == "fast"
        assert args.iterations == 7000
        assert args.device == "mps"

    def test_sharp_command(self):
        """sharp sub-command in image mode (default)."""
        from app.cli.parser import get_parser
        parser = get_parser()
        args = parser.parse_args([
            "sharp",
            "-i", "/input/photo.jpg",
            "-o", "/output",
        ])
        assert args.command == "sharp"
        assert args.mode == "image"

    def test_sharp_video_command(self):
        """sharp sub-command in video mode."""
        from app.cli.parser import get_parser
        parser = get_parser()
        args = parser.parse_args([
            "sharp",
            "-i", "/input/video.mp4",
            "-o", "/output",
            "--mode", "video",
            "--skip_frames", "3",
        ])
        assert args.command == "sharp"
        assert args.mode == "video"
        assert args.skip_frames == 3

    def test_upscale_command(self):
        """upscale sub-command."""
        from app.cli.parser import get_parser
        parser = get_parser()
        args = parser.parse_args([
            "upscale",
            "-i", "/input/image.png",
            "-o", "/output",
            "--model", "realesrgan-x4plus",
            "--scale", "4",
            "--format", "png",
        ])
        assert args.command == "upscale"
        assert args.model == "realesrgan-x4plus"
        assert args.scale == 4
        assert args.format == "png"

    def test_4dgs_command(self):
        """4dgs sub-command."""
        from app.cli.parser import get_parser
        parser = get_parser()
        args = parser.parse_args([
            "4dgs",
            "-i", "/input/videos",
            "-o", "/output",
            "--fps", "10",
        ])
        assert args.command == "4dgs"
        assert args.fps == 10

    def test_view_command(self):
        """view sub-command."""
        from app.cli.parser import get_parser
        parser = get_parser()
        args = parser.parse_args([
            "view",
            "-i", "/input/splat.ply",
            "--port", "8080",
        ])
        assert args.command == "view"
        assert args.port == 8080

    def test_extract360_command(self):
        """extract360 sub-command."""
        from app.cli.parser import get_parser
        parser = get_parser()
        args = parser.parse_args([
            "extract360",
            "-i", "/input/360.mp4",
            "-o", "/output",
            "--camera_count", "8",
        ])
        assert args.command == "extract360"
        assert args.camera_count == 8

    def test_help_shows_all_subcommands(self):
        """--help shows the sub-commands (checked through SystemExit)."""
        from app.cli.parser import get_parser
        parser = get_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--help"])
        assert exc_info.value.code == 0


# ─────────────────────────────────────────────────────────────────────────────
# CLI dispatch tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCLIDispatch:
    """Tests of the main() dispatch with mocked handlers."""

    def test_main_no_args_launches_gui(self):
        """main() without argument → _launch_gui() is called."""
        with patch("app.cli._launch_gui") as mock_gui, patch("app.cli.check_dependencies", return_value=[]):
            with patch.object(sys, "argv", ["main.py"]):
                from app.cli import main
                main()
                mock_gui.assert_called_once()

    def test_main_gui_flag(self):
        """main() with --gui → _launch_gui() is called."""
        with patch("app.cli._launch_gui") as mock_gui, patch("app.cli.check_dependencies", return_value=[]):
            with patch.object(sys, "argv", ["main.py", "--gui"]):
                from app.cli import main
                main()
                mock_gui.assert_called_once()

    def test_main_pipeline_dispatch(self):
        """main() with pipeline → run_pipeline is called."""
        with patch("app.cli.DISPATCH", new_callable=dict) as mock_dispatch:
            handler = MagicMock()
            mock_dispatch["pipeline"] = handler

            with patch("app.cli.check_dependencies", return_value=[]):
                with patch.object(sys, "argv", ["main.py", "pipeline", "-i", "/in", "-o", "/out"]):
                    from app.cli import main
                    main()
                    handler.assert_called_once()

    def test_main_colmap_dispatch(self):
        """main() with colmap → run_colmap is called."""
        with patch("app.cli.DISPATCH", new_callable=dict) as mock_dispatch:
            handler = MagicMock()
            mock_dispatch["colmap"] = handler

            with patch("app.cli.check_dependencies", return_value=[]):
                with patch.object(sys, "argv", ["main.py", "colmap", "-i", "/in", "-o", "/out"]):
                    from app.cli import main
                    main()
                    handler.assert_called_once()

    def test_main_unknown_command_shows_help(self):
        """Unknown command → print_help() is called."""
        with patch("app.cli.get_parser") as mock_get_parser, patch("app.cli.DISPATCH", new_callable=dict):
            mock_parser = MagicMock()
            mock_get_parser.return_value = mock_parser
            mock_args = MagicMock()
            mock_args.command = "unknown"
            mock_args.gui = False
            mock_parser.parse_args.return_value = mock_args

            with patch("app.cli.check_dependencies", return_value=[]), patch.object(sys, "exit"):
                from app.cli import main
                main()
                mock_parser.print_help.assert_called_once()

    def test_main_sharp_dispatch(self):
        """main() with sharp → run_sharp is called."""
        with patch("app.cli.DISPATCH", new_callable=dict) as mock_dispatch:
            handler = MagicMock()
            mock_dispatch["sharp"] = handler

            with patch("app.cli.check_dependencies", return_value=[]):
                with patch.object(sys, "argv", ["main.py", "sharp", "-i", "/in.jpg", "-o", "/out"]):
                    from app.cli import main
                    main()
                    handler.assert_called_once()

    def test_main_dependencies_missing(self):
        """Missing dependencies → message printed (with a sub-command)."""
        with patch("app.cli.DISPATCH", new_callable=dict) as mock_dispatch:
            handler = MagicMock()
            mock_dispatch["pipeline"] = handler
            with patch("app.cli.check_dependencies", return_value=["ffmpeg", "colmap"]):
                with patch("builtins.print") as mock_print:
                    with patch.object(sys, "argv", ["main.py", "pipeline", "-i", "/in", "-o", "/out"]):
                        from app.cli import main
                        with patch.object(sys, "exit"):
                            main()
                            # Should print about missing deps
                            mock_print.assert_any_call(
                                "Attention : dépendances manquantes : ffmpeg, colmap"
                            )


class TestRunFunctions:
    """Unit tests of the run_* functions with mocks."""

    @patch("app.cli.commands.ColmapEngine")
    @patch("app.cli.commands.ColmapParams")
    def test_run_colmap(self, mock_params_cls, mock_engine_cls):
        """run_colmap runs the COLMAP engine."""
        mock_engine = MagicMock()
        mock_engine.run.return_value = (True, "Success")
        mock_engine_cls.return_value = mock_engine

        args = MagicMock()
        args.camera_model = "SIMPLE_RADIAL"
        args.no_single_camera = False
        args.max_image_size = 3200
        args.max_num_features = 8192
        args.estimate_affine_shape = False
        args.no_domain_size_pooling = False
        args.max_ratio = 0.8
        args.max_distance = 0.7
        args.no_cross_check = False
        args.no_refine_focal = False
        args.refine_principal = False
        args.no_refine_extra = False
        args.min_num_matches = 15
        args.matcher_type = "exhaustive"
        args.undistort = False
        args.input = "/in"
        args.output = "/out"
        args.type = "images"
        args.fps = 5
        args.project_name = "Untitled"

        from app.cli.commands import run_colmap
        run_colmap(args)

        mock_engine_cls.assert_called_once()
        mock_engine.run.assert_called_once()

    @patch("app.cli.commands.BrushEngine")
    @patch("app.cli.commands.get_brush_build_mode")
    def test_run_brush(self, mock_get_mode, mock_engine_cls):
        """run_brush runs the Brush training."""
        mock_engine = MagicMock()
        mock_engine.train.return_value = 0
        mock_engine_cls.return_value = mock_engine
        mock_get_mode.return_value = "release"

        args = MagicMock()
        args.preset = "default"
        args.iterations = None
        args.sh_degree = None
        args.start_iter = None
        args.refine_every = None
        args.growth_grad_threshold = None
        args.growth_select_fraction = None
        args.growth_stop_iter = None
        args.max_splats = None
        args.checkpoint_interval = None
        args.max_resolution = None
        args.device = "auto"
        args.refine_mode = False
        args.with_viewer = False
        args.custom_args = None
        args.ply_name = None
        args.input = "/in"
        args.output = "/out"

        from app.cli.commands import run_brush
        run_brush(args)

        mock_engine.train.assert_called_once()

    @patch("app.cli.commands.SharpEngine")
    def test_run_sharp_image(self, mock_engine_cls):
        """run_sharp in image mode runs predict()."""
        mock_engine = MagicMock()
        mock_engine.predict.return_value = 0
        mock_engine_cls.return_value = mock_engine

        args = MagicMock()
        args.mode = "image"
        args.checkpoint = None
        args.device = "default"
        args.verbose = False
        args.input = "/in/photo.jpg"
        args.output = "/out"

        from app.cli.commands import run_sharp
        run_sharp(args)

        mock_engine.predict.assert_called_once()

    @patch("app.cli.commands.SharpEngine")
    def test_run_sharp_video(self, mock_engine_cls):
        """run_sharp in video mode runs process_video_frames()."""
        mock_engine = MagicMock()
        mock_engine.process_video_frames.return_value = 10
        mock_engine_cls.return_value = mock_engine

        args = MagicMock()
        args.mode = "video"
        args.checkpoint = None
        args.device = "default"
        args.verbose = False
        args.input = "/in/video.mp4"
        args.output = "/out"
        args.skip_frames = 1

        from app.cli.commands import run_sharp
        run_sharp(args)

        mock_engine.process_video_frames.assert_called_once()


class TestPipelineRun:
    """Tests for run_pipeline (full COLMAP → Brush pipeline)."""

    @patch("app.cli.commands.ColmapEngine")
    @patch("app.cli.commands.BrushEngine")
    @patch("app.cli.commands.get_brush_build_mode")
    def test_pipeline_success(self, mock_get_mode, mock_brush_cls, mock_colmap_cls):
        """Full pipeline succeeded."""
        mock_colmap = MagicMock()
        mock_colmap.run.return_value = (True, "Dataset ready")
        mock_colmap_cls.return_value = mock_colmap

        mock_brush = MagicMock()
        mock_brush.train.return_value = 0
        mock_brush_cls.return_value = mock_brush
        mock_get_mode.return_value = "release"

        args = MagicMock()
        args.input = "/in"
        args.output = "/out"
        args.project_name = "test"
        args.type = "images"
        args.fps = 5
        args.camera_model = "SIMPLE_RADIAL"
        args.matcher_type = "exhaustive"
        args.max_image_size = 3200
        args.undistort = False
        args.preset = "default"
        args.iterations = None
        args.sh_degree = None
        args.max_resolution = None
        args.device = "auto"
        args.with_viewer = False
        args.ply_name = None

        from app.cli.commands import run_pipeline
        run_pipeline(args)

        mock_colmap.run.assert_called_once()
        mock_brush.train.assert_called_once()


class TestRobustMode:
    """Tests for the robust mode (COLMAP anti-crash)."""

    def test_apply_robust_sets_stable_params(self):
        from app.cli.commands import _apply_robust
        from app.core.params import ColmapParams
        p = _apply_robust(ColmapParams(camera_model="SIMPLE_RADIAL"))
        assert p.camera_model == "PINHOLE"
        assert p.ba_refine_extra_params is False
        assert p.ba_refine_principal_point is False
        assert p.filter_blurry is True

    def test_robust_flag_parses(self):
        from app.cli.parser import get_parser
        args = get_parser().parse_args(["colmap", "-i", "x", "-o", "y", "--robust"])
        assert args.robust is True

    def test_blur_flag_parses(self):
        from app.cli.parser import get_parser
        args = get_parser().parse_args(["colmap", "-i", "x", "-o", "y", "--filter_blur", "--blur_strength", "strong"])
        assert args.filter_blur is True
        assert args.blur_strength == "strong"
