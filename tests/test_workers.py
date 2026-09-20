"""Tests for app/gui/workers.py — BaseWorker and the specialised workers.
"""
import os
import sys
import time
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest

from app.gui.base_worker import BaseWorker
from app.gui.workers import (
    BrushWorker,
    ColmapWorker,
    Extractor360Worker,
    SharpVideoWorker,
    SharpWorker,
)

# Patch send2trash and cv2 for the workers that use them indirectly
for _mod_name in ["send2trash", "cv2"]:
    if _mod_name not in sys.modules:
        try:
            __import__(_mod_name)  # keep real module if installed — avoids clobbering cv2/numpy session-wide
        except ImportError:
            sys.modules[_mod_name] = MagicMock()


# ─────────────────────────────────────────────────────────────────────────────
# BaseWorker tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBaseWorker:
    """Tests for BaseWorker — signals and lifecycle."""

    def test_base_worker_signals(self):
        """BaseWorker exposes the standard signals."""
        # Check the class has the expected signal attributes
        assert hasattr(BaseWorker, 'log_signal')
        assert hasattr(BaseWorker, 'progress_signal')
        assert hasattr(BaseWorker, 'status_signal')
        assert hasattr(BaseWorker, 'finished_signal')

    def test_base_worker_init(self):
        """Check that the signals are Signal instances."""
        # Signals should be Signal instances (class-level descriptors)
        import PySide6.QtCore
        assert isinstance(BaseWorker.log_signal, PySide6.QtCore.Signal)
        assert isinstance(BaseWorker.progress_signal, PySide6.QtCore.Signal)
        assert isinstance(BaseWorker.status_signal, PySide6.QtCore.Signal)
        assert isinstance(BaseWorker.finished_signal, PySide6.QtCore.Signal)

    def test_stop_sets_flags(self):
        """stop() met is_running=False et stopped_by_user=True."""
        with patch("app.gui.base_worker.QThread.__init__", return_value=None):
            worker = BaseWorker()
            worker.is_running = True
            worker.stopped_by_user = False
            worker.process = None

            worker.stop()
            assert worker.is_running is False
            assert worker.stopped_by_user is True


# ─────────────────────────────────────────────────────────────────────────────
# ColmapWorker tests
# ─────────────────────────────────────────────────────────────────────────────

class TestColmapWorker:
    """Tests for ColmapWorker with a mocked IProcessRunner."""

    @pytest.fixture
    def mock_engine(self):
        """Build a mocked ColmapEngine."""
        engine = MagicMock()
        engine.run.return_value = (True, "Success")
        return engine

    def test_run_success(self, mock_engine):
        """ColmapWorker.run() with a mocked engine → finished_signal with True."""
        worker = ColmapWorker.__new__(ColmapWorker)
        with patch.object(worker, 'isInterruptionRequested', return_value=False):
            with patch.object(worker, 'log_signal', MagicMock()):
                with patch.object(worker, 'progress_signal', MagicMock()):
                    with patch.object(worker, 'status_signal', MagicMock()):
                        with patch.object(worker, 'finished_signal', MagicMock()):
                            worker.engine = mock_engine
                            worker.upscale_params = None
                            worker.extractor_360_params = None

                            worker.run()
                            mock_engine.run.assert_called_once()
                            worker.finished_signal.emit.assert_called_once_with(True, "Success")

    def test_run_failure(self, mock_engine):
        """ColmapWorker.run() on failure → finished_signal with False."""
        mock_engine.run.return_value = (False, "Error: feature extraction failed")
        worker = ColmapWorker.__new__(ColmapWorker)
        with patch.object(worker, 'isInterruptionRequested', return_value=False):
            with patch.object(worker, 'log_signal', MagicMock()):
                with patch.object(worker, 'progress_signal', MagicMock()):
                    with patch.object(worker, 'status_signal', MagicMock()):
                        with patch.object(worker, 'finished_signal', MagicMock()):
                            worker.engine = mock_engine
                            worker.upscale_params = None
                            worker.extractor_360_params = None

                            worker.run()
                            worker.finished_signal.emit.assert_called_once_with(
                                False, "Error: feature extraction failed"
                            )

    def test_stop_calls_engine_stop(self, mock_engine):
        """stop() appelle engine.stop()."""
        worker = ColmapWorker.__new__(ColmapWorker)
        worker.process = None  # Avoids AttributeError in BaseWorker.stop()
        with patch.object(worker, 'log_signal', MagicMock()):
            with patch.object(worker, 'finished_signal', MagicMock()):
                with patch.object(worker, 'status_signal', MagicMock()):
                    worker.engine = mock_engine
                    worker.extractor_engine = None

                    with patch.object(worker, 'requestInterruption') as mock_req:
                        worker.stop()
                        mock_engine.stop.assert_called_once()
                        mock_req.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# BrushWorker tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBrushWorker:
    """Tests for BrushWorker."""

    @pytest.fixture
    def mock_engine(self):
        """Build a mocked BrushEngine."""
        engine = MagicMock()
        engine.train.return_value = 0
        return engine

    def test_resolve_dataset_root_sparse_0(self):
        """resolve_dataset_root with sparse/0 → goes up 2 levels."""
        worker = BrushWorker.__new__(BrushWorker)
        with patch.object(worker, 'log_signal', MagicMock()):
            with patch.object(worker, 'finished_signal', MagicMock()):
                path = Path("/project/scene/sparse/0")
                resolved = worker.resolve_dataset_root(path)
                assert resolved == Path("/project/scene")

    def test_resolve_dataset_root_sparse(self):
        """resolve_dataset_root with sparse → goes up 1 level."""
        worker = BrushWorker.__new__(BrushWorker)
        with patch.object(worker, 'log_signal', MagicMock()):
            with patch.object(worker, 'finished_signal', MagicMock()):
                path = Path("/project/scene/sparse")
                resolved = worker.resolve_dataset_root(path)
                assert resolved == Path("/project/scene")

    def test_resolve_dataset_root_normal(self):
        """resolve_dataset_root with a normal path → unchanged."""
        worker = BrushWorker.__new__(BrushWorker)
        with patch.object(worker, 'log_signal', MagicMock()):
            with patch.object(worker, 'finished_signal', MagicMock()):
                path = Path("/project/scene")
                resolved = worker.resolve_dataset_root(path)
                assert resolved == path

    def test_run_missing_dataset(self, mock_engine):
        """run() with a non-existent dataset → finished_signal(False)."""
        worker = BrushWorker.__new__(BrushWorker)
        with patch.object(worker, 'log_signal', MagicMock()):
            with patch.object(worker, 'status_signal', MagicMock()):
                with patch.object(worker, 'finished_signal', MagicMock()):
                    with patch.object(worker, 'isInterruptionRequested', return_value=False):
                        worker.engine = mock_engine
                        worker.input_path = "/nonexistent/path"
                        worker.output_path = "/output"
                        worker.params = {}
                        worker.project_name = ""

                        worker.run()
                        args, _ = worker.finished_signal.emit.call_args
                        assert args[0] is False
                        assert "n'existe pas" in args[1]

    def test_run_success(self, mock_engine, tmp_path):
        """run() with a valid dataset → finished_signal(True)."""
        dataset_dir = tmp_path / "dataset"
        dataset_dir.mkdir()

        worker = BrushWorker.__new__(BrushWorker)
        with patch.object(worker, 'log_signal', MagicMock()):
            with patch.object(worker, 'status_signal', MagicMock()):
                with patch.object(worker, 'finished_signal', MagicMock()):
                    with patch.object(worker, 'isInterruptionRequested', return_value=False):
                        worker.engine = mock_engine
                        worker.input_path = str(dataset_dir)
                        worker.output_path = str(tmp_path / "output")
                        worker.params = {"refine_mode": False}
                        worker.project_name = ""
                        worker.keep_only_latest = False

                        worker.run()
                        mock_engine.train.assert_called_once()
                        worker.finished_signal.emit.assert_called_once_with(True, ANY)

    def test_handle_ply_rename(self, mock_engine, tmp_path):
        """handle_ply_rename renames the PLY file."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "iteration_30000.ply").write_bytes(b"ply_data")

        worker = BrushWorker.__new__(BrushWorker)
        with patch.object(worker, 'log_signal', MagicMock()):
            with patch.object(worker, 'finished_signal', MagicMock()):
                worker.output_path = str(output_dir)
                worker.params = {"ply_name": "my_splat.ply", "total_steps": 30000}

                worker.handle_ply_rename()
                assert (output_dir / "my_splat.ply").exists()
                assert not (output_dir / "iteration_30000.ply").exists()

    def test_handle_ply_rename_no_name(self, mock_engine):
        """handle_ply_rename without ply_name → does nothing."""
        worker = BrushWorker.__new__(BrushWorker)
        with patch.object(worker, 'log_signal', MagicMock()):
            worker.params = {}
            worker.handle_ply_rename()

    def test_rename_checkpoints_with_project_name(self, tmp_path):
        """_rename_checkpoints_with_project_name prefixes the PLY files."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "iteration_1000.ply").write_bytes(b"data")
        (output_dir / "iteration_2000.ply").write_bytes(b"data")

        worker = BrushWorker.__new__(BrushWorker)
        with patch.object(worker, 'log_signal', MagicMock()):
            worker.output_path = str(output_dir)
            worker.project_name = "test_scene"

            worker._rename_checkpoints_with_project_name()
            assert (output_dir / "test_scene_iteration_1000.ply").exists()
            assert (output_dir / "test_scene_iteration_2000.ply").exists()

    def test_prune_to_latest_checkpoint(self, tmp_path):
        """_prune_to_latest_checkpoint keeps only the most recent PLY and purges the empty folders."""
        output_dir = tmp_path / "output"
        (output_dir / "point_cloud" / "iteration_1000").mkdir(parents=True)
        (output_dir / "point_cloud" / "iteration_2000").mkdir(parents=True)
        old = output_dir / "point_cloud" / "iteration_1000" / "point_cloud.ply"
        new = output_dir / "point_cloud" / "iteration_2000" / "point_cloud.ply"
        old.write_bytes(b"old")
        new.write_bytes(b"new")
        # Force a more recent mtime for `new`
        os.utime(old, (1000, 1000))
        os.utime(new, (2000, 2000))

        worker = BrushWorker.__new__(BrushWorker)
        with patch.object(worker, 'log_signal', MagicMock()):
            worker.output_path = str(output_dir)

            worker._prune_to_latest_checkpoint()
            assert new.exists()
            assert not old.exists()
            # The empty folder of the old checkpoint is removed
            assert not (output_dir / "point_cloud" / "iteration_1000").exists()

    def test_prune_to_latest_checkpoint_single(self, tmp_path):
        """_prune_to_latest_checkpoint with a single PLY → removes nothing."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        only = output_dir / "iteration_1000.ply"
        only.write_bytes(b"data")

        worker = BrushWorker.__new__(BrushWorker)
        with patch.object(worker, 'log_signal', MagicMock()):
            worker.output_path = str(output_dir)

            worker._prune_to_latest_checkpoint()
            assert only.exists()

    def test_run_archives_only_checkpoint_plys_not_whole_directory(self, mock_engine, tmp_path):
        """run() in "new" mode only archives the .ply files, never the
        output_path folder itself. Regression: a wrong output_path (e.g. the
        OUTILS Brush module pointed at a project folder holding other
        sub-folders) made the whole tree move through shutil.move on the entire
        folder, instead of the checkpoints alone.
        """
        output_dir = tmp_path / "output"
        old_ckpt = output_dir / "point_cloud" / "iteration_1000" / "point_cloud.ply"
        old_ckpt.parent.mkdir(parents=True)
        old_ckpt.write_bytes(b"old")
        unrelated_dir = output_dir / "unrelated_project"
        unrelated_dir.mkdir()
        unrelated_file = unrelated_dir / "keepme.txt"
        unrelated_file.write_text("do not touch")

        dataset_dir = tmp_path / "dataset"
        dataset_dir.mkdir()

        worker = BrushWorker.__new__(BrushWorker)
        with patch.object(worker, 'log_signal', MagicMock()):
            with patch.object(worker, 'status_signal', MagicMock()):
                with patch.object(worker, 'finished_signal', MagicMock()):
                    with patch.object(worker, 'isInterruptionRequested', return_value=False):
                        worker.engine = mock_engine
                        worker.input_path = str(dataset_dir)
                        worker.output_path = str(output_dir)
                        worker.params = {"refine_mode": False}
                        worker.project_name = ""
                        worker.keep_only_latest = False

                        worker.run()

        # The output directory itself is never moved/renamed.
        assert output_dir.exists()
        # Unrelated content stays exactly where it was.
        assert unrelated_file.exists()
        assert unrelated_file.read_text() == "do not touch"
        # The old checkpoint is gone from its original location...
        assert not old_ckpt.exists()
        # ...archived under a sibling backup folder, same relative subpath.
        backups = list(tmp_path.glob("checkpoints_backup_*"))
        assert len(backups) == 1
        assert (backups[0] / "point_cloud" / "iteration_1000" / "point_cloud.ply").exists()

    def test_run_no_archive_when_no_existing_checkpoints(self, mock_engine, tmp_path):
        """run() in "new" mode with no existing checkpoint → no backup created."""
        output_dir = tmp_path / "output"
        dataset_dir = tmp_path / "dataset"
        dataset_dir.mkdir()

        worker = BrushWorker.__new__(BrushWorker)
        with patch.object(worker, 'log_signal', MagicMock()):
            with patch.object(worker, 'status_signal', MagicMock()):
                with patch.object(worker, 'finished_signal', MagicMock()):
                    with patch.object(worker, 'isInterruptionRequested', return_value=False):
                        worker.engine = mock_engine
                        worker.input_path = str(dataset_dir)
                        worker.output_path = str(output_dir)
                        worker.params = {"refine_mode": False}
                        worker.project_name = ""
                        worker.keep_only_latest = False

                        worker.run()

        assert not list(tmp_path.glob("checkpoints_backup_*"))


# ─────────────────────────────────────────────────────────────────────────────
# SharpWorker tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSharpWorker:
    """Tests for SharpWorker."""

    def test_run_success(self):
        """SharpWorker.run() with a mocked engine."""
        engine = MagicMock()
        engine.predict.return_value = 0

        worker = SharpWorker.__new__(SharpWorker)
        with patch.object(worker, 'log_signal', MagicMock()):
            with patch.object(worker, 'status_signal', MagicMock()):
                with patch.object(worker, 'finished_signal', MagicMock()):
                    with patch.object(worker, 'isInterruptionRequested', return_value=False):
                        worker.engine = engine
                        worker.input_path = "/in.jpg"
                        worker.output_path = "/out"
                        worker.params = {}

                        worker.run()
                        engine.predict.assert_called_once()

    def test_run_failure(self):
        """SharpWorker.run() on failure."""
        engine = MagicMock()
        engine.predict.return_value = 1

        worker = SharpWorker.__new__(SharpWorker)
        with patch.object(worker, 'log_signal', MagicMock()):
            with patch.object(worker, 'status_signal', MagicMock()):
                with patch.object(worker, 'finished_signal', MagicMock()):
                    with patch.object(worker, 'isInterruptionRequested', return_value=False):
                        worker.engine = engine
                        worker.input_path = "/in.jpg"
                        worker.output_path = "/out"
                        worker.params = {}

                        worker.run()
                        args, _ = worker.finished_signal.emit.call_args
                        assert args[0] is False


# ─────────────────────────────────────────────────────────────────────────────
# SharpVideoWorker tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSharpVideoWorker:
    """Tests for SharpVideoWorker."""

    def test_run_success(self):
        """SharpVideoWorker.run() with a mocked engine."""
        engine = MagicMock()
        engine.process_video_frames.return_value = 5

        worker = SharpVideoWorker.__new__(SharpVideoWorker)
        with patch.object(worker, 'log_signal', MagicMock()):
            with patch.object(worker, 'status_signal', MagicMock()):
                with patch.object(worker, 'progress_signal', MagicMock()):
                    with patch.object(worker, 'finished_signal', MagicMock()):
                        with patch.object(worker, 'isInterruptionRequested', return_value=False):
                            worker.engine = engine
                            worker.video_path = "/in.mp4"
                            worker.output_path = "/out"
                            worker.params = {}

                            worker.run()
                            engine.process_video_frames.assert_called_once()
                            args, _ = worker.finished_signal.emit.call_args
                            assert args[0] is True

    def test_run_no_frames(self):
        """SharpVideoWorker.run() with no processed frame."""
        engine = MagicMock()
        engine.process_video_frames.return_value = 0

        worker = SharpVideoWorker.__new__(SharpVideoWorker)
        with patch.object(worker, 'log_signal', MagicMock()):
            with patch.object(worker, 'status_signal', MagicMock()):
                with patch.object(worker, 'progress_signal', MagicMock()):
                    with patch.object(worker, 'finished_signal', MagicMock()):
                        with patch.object(worker, 'isInterruptionRequested', return_value=False):
                            worker.engine = engine
                            worker.video_path = "/in.mp4"
                            worker.output_path = "/out"
                            worker.params = {}

                            worker.run()
                            args, _ = worker.finished_signal.emit.call_args
                            assert args[0] is False
                            assert "Aucune frame" in args[1]


# ─────────────────────────────────────────────────────────────────────────────
# Extractor360Worker tests
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractor360Worker:
    """Tests for Extractor360Worker."""

    def test_parse_line_percentage(self):
        """parse_line extracts the [XX%] percentage."""
        worker = Extractor360Worker.__new__(Extractor360Worker)
        with patch.object(worker, 'progress_signal', MagicMock()):
            worker.parse_line("[42%] Processing frame 42")
            worker.progress_signal.emit.assert_called_once_with(42)

    def test_parse_line_no_percentage(self):
        """parse_line without a percentage → no call."""
        worker = Extractor360Worker.__new__(Extractor360Worker)
        with patch.object(worker, 'progress_signal', MagicMock()):
            worker.parse_line("Starting extraction...")
            worker.progress_signal.emit.assert_not_called()


class TestBrushCheckpointProgress:
    """_start_checkpoint_progress: progress inferred from exported checkpoints."""

    def _worker(self, tmp_path, params):
        worker = BrushWorker.__new__(BrushWorker)
        worker.params = params
        worker.output_path = tmp_path
        return worker

    def test_returns_none_without_usable_interval(self, tmp_path):
        """No step count or a disabled export interval → no estimate at all."""
        for params in (
            {"total_steps": 30000, "checkpoint_interval": 0},
            {"total_steps": None, "checkpoint_interval": 7000},
            {},
        ):
            worker = self._worker(tmp_path, params)
            assert worker._start_checkpoint_progress() is None

    def test_preexisting_checkpoints_are_not_counted(self, tmp_path):
        """A resumed run must not start out looking already complete."""
        for i in range(4):
            (tmp_path / f"old_{i}.ply").write_bytes(b"")
        worker = self._worker(
            tmp_path, {"total_steps": 28000, "checkpoint_interval": 7000}
        )
        emitted = []
        with patch.object(worker, "progress_signal", MagicMock()) as sig:
            sig.emit.side_effect = emitted.append
            stop = worker._start_checkpoint_progress(poll_interval=0.02)
            assert stop is not None
            try:
                (tmp_path / "new_0.ply").write_bytes(b"")
                deadline = time.time() + 10
                while not emitted and time.time() < deadline:
                    time.sleep(0.1)
            finally:
                stop.set()
        assert emitted, "poller never reported progress"
        # 1 new checkpoint out of 4 expected, the 4 preexisting ones ignored.
        assert emitted[0] == 25

    def test_progress_is_capped_below_completion(self, tmp_path):
        """More checkpoints than expected must not report a finished run."""
        worker = self._worker(
            tmp_path, {"total_steps": 14000, "checkpoint_interval": 7000}
        )
        emitted = []
        with patch.object(worker, "progress_signal", MagicMock()) as sig:
            sig.emit.side_effect = emitted.append
            stop = worker._start_checkpoint_progress(poll_interval=0.02)
            try:
                for i in range(5):
                    (tmp_path / f"ckpt_{i}.ply").write_bytes(b"")
                deadline = time.time() + 10
                while not emitted and time.time() < deadline:
                    time.sleep(0.1)
            finally:
                stop.set()
        assert emitted and emitted[0] == 99
