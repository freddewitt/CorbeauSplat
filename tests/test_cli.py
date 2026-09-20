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
    def test_pipeline_success(self, mock_get_mode, mock_brush_cls, mock_colmap_cls, tmp_path):
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
        args.output = str(tmp_path / "out")
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

        # Brush must write where the GUI would look: <output>/<project>/checkpoints.
        # The CLI used to hand it the dataset folder instead, so a project moved
        # between the two interfaces lost track of its checkpoints (audit I9).
        expected = tmp_path / "out" / "test" / "checkpoints"
        assert mock_brush.train.call_args[0][1] == str(expected)
        assert expected.is_dir()


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


# ---------------------------------------------------------------------------
# ColmapParams <-> CLI flag parity (audit I10)
# ---------------------------------------------------------------------------

# Fields whose CLI flag is not named after them. Inverted booleans ("--no_x"
# for a field defaulting to True) and renames both live here.
COLMAP_FLAG_ALIASES = {
    "single_camera": "no_single_camera",
    "domain_size_pooling": "no_domain_size_pooling",
    "cross_check": "no_cross_check",
    "ba_refine_focal_length": "no_refine_focal",
    "ba_refine_principal_point": "refine_principal",
    "ba_refine_extra_params": "no_refine_extra",
    "filter_blurry": "filter_blur",
    "blur_factor": "blur_strength",
    "use_view_graph_calibration": "view_graph_calibration",
    "image_convert_format": "convert",
    "undistort_images": "undistort",
    "video_trim_start": "trim_start",
    "video_trim_end": "trim_end",
}


def _colmap_subparser_dests():
    import dataclasses  # noqa: F401  (kept local, mirrors the test's own imports)

    from app.cli.parser import get_parser

    parser = get_parser()
    subparsers = parser._subparsers._group_actions[0]
    return {action.dest for action in subparsers.choices["colmap"]._actions}


def test_every_colmap_param_has_a_cli_flag():
    """Each ColmapParams field must be reachable from `main.py colmap`.

    This is the drift guard the audit asked for. `sequential_overlap` and
    `guided_matching` had silently fallen out of the CLI: `_build_params` read
    them with `getattr(args, ..., default)`, so a missing flag produced no
    error, just a value the user could never change.
    """
    import dataclasses

    from app.core.params import ColmapParams

    dests = _colmap_subparser_dests()
    missing = [
        field.name
        for field in dataclasses.fields(ColmapParams)
        if field.name not in dests and COLMAP_FLAG_ALIASES.get(field.name) not in dests
    ]
    assert missing == [], f"ColmapParams fields with no CLI flag: {missing}"


def test_flag_aliases_still_point_at_real_flags():
    """Guard the guard: a stale alias would hide a genuinely missing flag."""
    dests = _colmap_subparser_dests()
    stale = [alias for alias in COLMAP_FLAG_ALIASES.values() if alias not in dests]
    assert stale == [], f"aliases pointing at flags that no longer exist: {stale}"


@pytest.mark.parametrize("flag,dest", [
    ("--no-view-graph-calibration", "view_graph_calibration"),
    ("--no-ignore-watermarks", "ignore_watermarks"),
])
def test_default_on_booleans_can_be_turned_off(flag, dest):
    """Both flags default to True; the negative form must actually disable them.

    They were declared as `store_true, default=True` with a hand-written twin,
    so the positive form was a no-op and the pair could drift apart.
    """
    from app.cli.parser import get_parser

    parser = get_parser()
    assert getattr(parser.parse_args(["colmap", "-i", "x", "-o", "y"]), dest) is True
    assert getattr(parser.parse_args(["colmap", "-i", "x", "-o", "y", flag]), dest) is False


def test_guided_matching_reaches_colmap_params():
    """The GUI exposed it and COLMAP consumes it, but the CLI dropped it."""
    from app.cli.commands import _build_colmap_params
    from app.cli.parser import get_parser

    parser = get_parser()
    off = _build_colmap_params(parser.parse_args(["colmap", "-i", "x", "-o", "y"]))
    on = _build_colmap_params(parser.parse_args(["colmap", "-i", "x", "-o", "y", "--guided_matching"]))
    assert off.guided_matching is False
    assert on.guided_matching is True


def test_sequential_overlap_reaches_colmap_params():
    from app.cli.commands import _build_colmap_params
    from app.cli.parser import get_parser

    parser = get_parser()
    params = _build_colmap_params(parser.parse_args(
        ["colmap", "-i", "x", "-o", "y", "--matcher_type", "sequential", "--sequential_overlap", "50"]
    ))
    assert params.sequential_overlap == 50


class TestPipelinePostSteps:
    """`pipeline` chains Cleaning and Export like the GUI does (audit I8)."""

    def _make_checkpoint(self, checkpoints_dir):
        """Write a PLY named the way Brush names its checkpoints."""
        import numpy as np
        from plyfile import PlyData, PlyElement

        checkpoints_dir.mkdir(parents=True, exist_ok=True)
        ply = checkpoints_dir / "export_30000.ply"
        names = ("x", "y", "z", "opacity", "scale_0", "scale_1", "scale_2",
                 "f_dc_0", "f_dc_1", "f_dc_2")
        verts = np.zeros(40, dtype=[(n, "f4") for n in names])
        verts["x"] = np.arange(40, dtype="f4")
        verts["opacity"] = 3.0          # sigmoid(3) ~ 0.95, well above any threshold
        verts["scale_0"] = verts["scale_1"] = verts["scale_2"] = -5.0
        PlyData([PlyElement.describe(verts, "vertex")]).write(str(ply))
        return ply

    def test_no_flags_means_no_extra_steps(self, tmp_path):
        from app.cli.commands import _run_pipeline_post_steps

        checkpoints = tmp_path / "checkpoints"
        self._make_checkpoint(checkpoints)
        args = MagicMock()
        args.clean = None
        args.export = None

        _run_pipeline_post_steps(args, checkpoints, 2)
        assert list(checkpoints.glob("*_cleaned.ply")) == []

    def test_clean_produces_a_cleaned_file(self, tmp_path):
        from app.cli.commands import _run_pipeline_post_steps

        checkpoints = tmp_path / "checkpoints"
        self._make_checkpoint(checkpoints)
        args = MagicMock()
        args.clean = "light"
        args.export = None

        _run_pipeline_post_steps(args, checkpoints, 3)
        assert (checkpoints / "export_30000_cleaned.ply").exists()

    def test_export_runs_on_the_cleaned_file_when_both_asked(self, tmp_path):
        """Order matters: export must consume the cleaned splat, not the raw one."""
        from app.cli.commands import _run_pipeline_post_steps

        checkpoints = tmp_path / "checkpoints"
        self._make_checkpoint(checkpoints)
        args = MagicMock()
        args.clean = "light"
        args.export = "xyz"
        args.export_output = str(tmp_path / "exported")

        _run_pipeline_post_steps(args, checkpoints, 4)
        assert (tmp_path / "exported" / "export_30000_cleaned.xyz").exists()

    def test_missing_checkpoint_is_reported_not_crashed(self, tmp_path, capsys):
        from app.cli.commands import _run_pipeline_post_steps

        empty = tmp_path / "checkpoints"
        empty.mkdir()
        args = MagicMock()
        args.clean = "light"
        args.export = None

        _run_pipeline_post_steps(args, empty, 3)
        assert "Aucun checkpoint" in capsys.readouterr().out

    def test_user_ply_is_not_mistaken_for_a_checkpoint(self, tmp_path):
        """Only files matching Brush's naming are eligible, per find_checkpoint_plys."""
        from app.cli.commands import _latest_checkpoint_ply

        checkpoints = tmp_path / "checkpoints"
        checkpoints.mkdir()
        (checkpoints / "mon_scan_perso.ply").write_text("not a checkpoint")
        assert _latest_checkpoint_ply(checkpoints) is None


def test_manifest_documents_every_subcommand():
    """manifest.md listed 9 of the 10 dispatch entries; `splattransform` was missing.

    Pinned here so the documentation cannot drift away from DISPATCH again.
    """
    from pathlib import Path

    from app.cli.commands import DISPATCH

    section = Path("manifest.md").read_text().split("## CLI Subcommands", 1)[1]
    section = section.split("##", 1)[0]
    undocumented = [name for name in DISPATCH if f"`{name}`" not in section]
    assert undocumented == [], f"subcommands missing from manifest.md: {undocumented}"


def test_every_subcommand_has_its_own_builder():
    """get_parser() was 302 lines declaring ten subcommands inline (audit M11).

    Each now has an `_add_<name>_parser` function, and get_parser() only calls
    them. Pinned so the next subcommand is not appended back into the body.
    """
    import inspect

    from app.cli import parser as parser_module
    from app.cli.commands import DISPATCH

    source = inspect.getsource(parser_module.get_parser)
    assert source.count("add_parser(") == 0, "a subcommand is declared inside get_parser()"

    for name in DISPATCH:
        builder = f"_add_{name}_parser"
        assert hasattr(parser_module, builder), f"missing builder: {builder}"
        assert f"{builder}(subs)" in source, f"{builder} is never called"


def test_get_parser_stays_short():
    """A guard on the shape, not the style: the body is a list of calls."""
    import inspect

    from app.cli.parser import get_parser

    assert len(inspect.getsource(get_parser).splitlines()) < 60
