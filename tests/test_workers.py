"""Tests pour app/gui/workers.py — BaseWorker et workers spécialisés."""
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, ANY

import pytest

# PyQt6 et send2trash peuvent ne pas être installés → on skip les tests qui en dépendent
try:
    from app.gui.base_worker import BaseWorker
    from app.gui.workers import (
        ColmapWorker, BrushWorker, Extractor360Worker,
    )
    WORKERS_AVAILABLE = True
except (ImportError, AttributeError, ModuleNotFoundError) as e:
    WORKERS_AVAILABLE = False
    WORKERS_REASON = f"Module manquant: {e}"

# Patch send2trash et cv2 pour les workers qui les utilisent indirectement
for _mod_name in ["send2trash", "cv2"]:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = MagicMock()


# ─────────────────────────────────────────────────────────────────────────────
# BaseWorker tests
# ─────────────────────────────────────────────────────────────────────────────

class TestBaseWorker:
    """Tests pour BaseWorker — signaux et cycle de vie."""

    def test_base_worker_signals(self):
        """BaseWorker expose les signaux standard."""
        if not WORKERS_AVAILABLE:
            pytest.skip(WORKERS_REASON)
        # Check the class has the expected signal attributes
        assert hasattr(BaseWorker, 'log_signal')
        assert hasattr(BaseWorker, 'progress_signal')
        assert hasattr(BaseWorker, 'status_signal')
        assert hasattr(BaseWorker, 'finished_signal')

    def test_base_worker_init(self):
        """Vérifie que les signaux sont des pyqtSignal."""
        if not WORKERS_AVAILABLE:
            pytest.skip(WORKERS_REASON)
        # Signals should be pyqtSignal instances (class-level descriptors)
        import PyQt6.QtCore
        assert isinstance(BaseWorker.log_signal, PyQt6.QtCore.pyqtSignal)
        assert isinstance(BaseWorker.progress_signal, PyQt6.QtCore.pyqtSignal)
        assert isinstance(BaseWorker.status_signal, PyQt6.QtCore.pyqtSignal)
        assert isinstance(BaseWorker.finished_signal, PyQt6.QtCore.pyqtSignal)

    def test_stop_sets_flags(self):
        """stop() met is_running=False et stopped_by_user=True."""
        if not WORKERS_AVAILABLE:
            pytest.skip(WORKERS_REASON)
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
    """Tests pour ColmapWorker avec IProcessRunner mocké."""

    @pytest.fixture
    def mock_engine(self):
        """Crée un ColmapEngine mocké."""
        engine = MagicMock()
        engine.run.return_value = (True, "Success")
        return engine

    def test_run_success(self, mock_engine):
        """ColmapWorker.run() avec moteur mocké → finished_signal avec True."""
        if not WORKERS_AVAILABLE:
            pytest.skip(WORKERS_REASON)
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
        """ColmapWorker.run() en échec → finished_signal avec False."""
        if not WORKERS_AVAILABLE:
            pytest.skip(WORKERS_REASON)
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
        if not WORKERS_AVAILABLE:
            pytest.skip(WORKERS_REASON)
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
    """Tests pour BrushWorker."""

    @pytest.fixture
    def mock_engine(self):
        """Crée un BrushEngine mocké."""
        engine = MagicMock()
        engine.train.return_value = 0
        return engine

    def test_resolve_dataset_root_sparse_0(self):
        """resolve_dataset_root avec sparse/0 → remonte de 2 niveaux."""
        if not WORKERS_AVAILABLE:
            pytest.skip(WORKERS_REASON)
        worker = BrushWorker.__new__(BrushWorker)
        with patch.object(worker, 'log_signal', MagicMock()):
            with patch.object(worker, 'finished_signal', MagicMock()):
                path = Path("/project/scene/sparse/0")
                resolved = worker.resolve_dataset_root(path)
                assert resolved == Path("/project/scene")

    def test_resolve_dataset_root_sparse(self):
        """resolve_dataset_root avec sparse → remonte de 1 niveau."""
        if not WORKERS_AVAILABLE:
            pytest.skip(WORKERS_REASON)
        worker = BrushWorker.__new__(BrushWorker)
        with patch.object(worker, 'log_signal', MagicMock()):
            with patch.object(worker, 'finished_signal', MagicMock()):
                path = Path("/project/scene/sparse")
                resolved = worker.resolve_dataset_root(path)
                assert resolved == Path("/project/scene")

    def test_resolve_dataset_root_normal(self):
        """resolve_dataset_root avec chemin normal → inchangé."""
        if not WORKERS_AVAILABLE:
            pytest.skip(WORKERS_REASON)
        worker = BrushWorker.__new__(BrushWorker)
        with patch.object(worker, 'log_signal', MagicMock()):
            with patch.object(worker, 'finished_signal', MagicMock()):
                path = Path("/project/scene")
                resolved = worker.resolve_dataset_root(path)
                assert resolved == path

    def test_run_missing_dataset(self, mock_engine):
        """run() avec dataset inexistant → finished_signal(False)."""
        if not WORKERS_AVAILABLE:
            pytest.skip(WORKERS_REASON)
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
        """run() avec dataset valide → finished_signal(True)."""
        if not WORKERS_AVAILABLE:
            pytest.skip(WORKERS_REASON)
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

                        worker.run()
                        mock_engine.train.assert_called_once()
                        worker.finished_signal.emit.assert_called_once_with(True, ANY)

    def test_handle_ply_rename(self, mock_engine, tmp_path):
        """handle_ply_rename renomme le fichier PLY."""
        if not WORKERS_AVAILABLE:
            pytest.skip(WORKERS_REASON)
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
        """handle_ply_rename sans ply_name → ne fait rien."""
        if not WORKERS_AVAILABLE:
            pytest.skip(WORKERS_REASON)
        worker = BrushWorker.__new__(BrushWorker)
        with patch.object(worker, 'log_signal', MagicMock()):
            worker.params = {}
            worker.handle_ply_rename()

    def test_rename_checkpoints_with_project_name(self, tmp_path):
        """_rename_checkpoints_with_project_name préfixe les PLY."""
        if not WORKERS_AVAILABLE:
            pytest.skip(WORKERS_REASON)
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


# ─────────────────────────────────────────────────────────────────────────────
# Extractor360Worker tests
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractor360Worker:
    """Tests pour Extractor360Worker."""

    def test_parse_line_percentage(self):
        """parse_line extrait le pourcentage [XX%]."""
        if not WORKERS_AVAILABLE:
            pytest.skip(WORKERS_REASON)
        worker = Extractor360Worker.__new__(Extractor360Worker)
        with patch.object(worker, 'progress_signal', MagicMock()):
            worker.parse_line("[42%] Processing frame 42")
            worker.progress_signal.emit.assert_called_once_with(42)

    def test_parse_line_no_percentage(self):
        """parse_line sans pourcentage → pas d'appel."""
        if not WORKERS_AVAILABLE:
            pytest.skip(WORKERS_REASON)
        worker = Extractor360Worker.__new__(Extractor360Worker)
        with patch.object(worker, 'progress_signal', MagicMock()):
            worker.parse_line("Starting extraction...")
            worker.progress_signal.emit.assert_not_called()
