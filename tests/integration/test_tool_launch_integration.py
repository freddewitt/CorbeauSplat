"""Integration tests: each TOOLS module triggers the right worker through
``StudioWindow._start_tool_worker()`` (point d'orchestration unique, lot 5).

Un test par module (+ cas « COLMAP seulement » de 4DGS) confirmant que le clic
sur le bouton Lancer local instancie le worker attendu, le démarre, et bascule
``SourcePanel`` (le bouton Lancer/Annuler unique, ex-topbar) en mode Annuler —
sans dépendre de vrais widgets Qt (cf. le pattern ``Worker.__new__(Worker)``
déjà utilisé dans ``test_workers.py``).
"""
import sys
from unittest.mock import MagicMock

from tests.conftest import _patch_pyqt6

_patch_pyqt6()

# StudioWindow(QMainWindow) must stay a real Python class, instantiable
# through __new__ (bypassing __init__, like the workers tested elsewhere):
# under the session-wide PySide6 mock, QtWidgets is a generic MagicMock whose
# attributes are not types usable as a base class. Only QMainWindow is
# replaced (the only base in use), before the first import of
# studio_window.py.
sys.modules["PySide6.QtWidgets"].QMainWindow = type("QMainWindow", (), {})

from app.gui import studio_window as sw  # noqa: E402


class _FakeLineEdit:
    """Substitut minimal de QLineEdit/DropLineEdit : juste .text()."""

    def __init__(self, text=""):
        self._text = text

    def text(self):
        return self._text


def _make_window():
    """StudioWindow without going through __init__ (no real Qt widgets needed)."""
    window = sw.StudioWindow.__new__(sw.StudioWindow)
    window._active_worker = None
    window.activity_bar = MagicMock()
    window.logs_window = MagicMock()
    # _start_tool_worker() names the current step in the activity bar from
    # the page on screen (PageRegistry.current).
    window.nav = MagicMock()
    window.nav.current = "upscale"
    # SourcePanel (formerly the topbar) now carries the single Launch/Cancel
    # button; _start_tool_worker() flips its state through set_running().
    window.panels = {"source": MagicMock()}
    return window


class TestToolLaunchOrchestration:
    """Every TOOLS module takes the same route: local button →
    ``_launch_*`` → ``_start_tool_worker`` (worker.start(), SourcePanel Annuler)."""

    def test_cleaner_launch_starts_cleaner_worker(self, monkeypatch):
        window = _make_window()
        mock_worker_cls = MagicMock()
        monkeypatch.setattr(sw, "CleanerWorker", mock_worker_cls)
        panel = MagicMock()
        panel.input_path = _FakeLineEdit("/in.ply")
        panel.output_path = _FakeLineEdit("/out.ply")
        panel.get_params.return_value = {"strength": "medium"}
        window.panels["nettoyage"] = panel

        window._launch_cleaner()

        mock_worker_cls.assert_called_once_with("/in.ply", "/out.ply", {"strength": "medium"})
        instance = mock_worker_cls.return_value
        instance.start.assert_called_once()
        assert window._active_worker is instance
        window.panels["source"].set_running.assert_called_once_with(True)

    def test_export_launch_starts_export_worker(self, monkeypatch):
        window = _make_window()
        mock_worker_cls = MagicMock()
        monkeypatch.setattr(sw, "ExportWorker", mock_worker_cls)
        panel = MagicMock()
        panel.input_path = _FakeLineEdit("/in1.ply|/in2.ply")
        panel.output_path = _FakeLineEdit("/out_dir")
        panel.get_format.return_value = "spz"
        panel.get_scale.return_value = 1.0
        window.panels["export"] = panel

        window._launch_export()

        mock_worker_cls.assert_called_once_with(
            ["/in1.ply", "/in2.ply"], "/out_dir", "spz", options={"scale": 1.0}
        )
        instance = mock_worker_cls.return_value
        instance.start.assert_called_once()
        assert window._active_worker is instance
        window.panels["source"].set_running.assert_called_once_with(True)

    def test_extractor360_launch_starts_extractor360_worker(self, monkeypatch):
        window = _make_window()
        mock_worker_cls = MagicMock()
        monkeypatch.setattr(sw, "Extractor360Worker", mock_worker_cls)
        panel = MagicMock()
        panel.input_path = _FakeLineEdit("/videos_dir")
        panel.output_path = _FakeLineEdit("/out_dir")
        panel.get_params.return_value = {"interval": 1}
        window.panels["extraction360"] = panel

        window._launch_extraction360()

        mock_worker_cls.assert_called_once_with("/videos_dir", "/out_dir", {"interval": 1})
        instance = mock_worker_cls.return_value
        instance.start.assert_called_once()
        assert window._active_worker is instance
        window.panels["source"].set_running.assert_called_once_with(True)

    def test_fourdgs_launch_starts_fourdgs_worker(self, monkeypatch):
        window = _make_window()
        mock_worker_cls = MagicMock()
        monkeypatch.setattr(sw, "FourDGSWorker", mock_worker_cls)
        panel = MagicMock()
        panel.get_params.return_value = {
            "input_path": "/videos_dir", "output_path": "/out_dir", "fps": 5, "upscale": False,
            "camera_model": "OPENCV", "single_camera": True,
            "matcher_type": "sequential", "sequential_overlap": 10,
        }
        upscale_panel = MagicMock()
        upscale_panel.get_params.return_value = {"scale": 4}
        window.panels["4dgs"] = panel
        window.panels["upscale"] = upscale_panel

        window._launch_fourdgs()

        mock_worker_cls.assert_called_once_with(
            "/videos_dir", "/out_dir", 5,
            upscale_params={"scale": 4, "active": False},
            colmap_params={
                "camera_model": "OPENCV", "single_camera": True,
                "matcher_type": "sequential", "sequential_overlap": 10,
            },
        )
        instance = mock_worker_cls.return_value
        instance.start.assert_called_once()
        assert window._active_worker is instance
        window.panels["source"].set_running.assert_called_once_with(True)

    def test_fourdgs_colmap_only_launch_starts_fourdgs_worker_without_videos(self, monkeypatch):
        """With "COLMAP reconstruction only" ticked, the field is ignored
        Source même rempli, FourDGSWorker reçoit videos_dir=None (mode COLMAP
        seul, cf. ancien FourDGSTab.run_colmap_only)."""
        window = _make_window()
        mock_worker_cls = MagicMock()
        monkeypatch.setattr(sw, "FourDGSWorker", mock_worker_cls)
        panel = MagicMock()
        panel.get_params.return_value = {
            "input_path": "/videos_dir", "output_path": "/out_dir", "fps": 5,
            "upscale": False, "colmap_only": True,
            "camera_model": "OPENCV", "single_camera": True,
            "matcher_type": "exhaustive", "sequential_overlap": 10,
        }
        upscale_panel = MagicMock()
        upscale_panel.get_params.return_value = {"scale": 4}
        window.panels["4dgs"] = panel
        window.panels["upscale"] = upscale_panel

        window._launch_fourdgs()

        mock_worker_cls.assert_called_once_with(
            None, "/out_dir", 5,
            upscale_params={"scale": 4, "active": False},
            colmap_params={
                "camera_model": "OPENCV", "single_camera": True,
                "matcher_type": "exhaustive", "sequential_overlap": 10,
            },
        )
        instance = mock_worker_cls.return_value
        instance.start.assert_called_once()
        assert window._active_worker is instance
        window.panels["source"].set_running.assert_called_once_with(True)

    def test_sharp_image_launch_starts_sharp_worker(self, monkeypatch):
        window = _make_window()
        mock_worker_cls = MagicMock()
        monkeypatch.setattr(sw, "SharpWorker", mock_worker_cls)
        panel = MagicMock()
        panel.get_params.return_value = {
            "mode": "image", "input_path": "/in.jpg", "output_path": "/out_dir",
            "video_path": "", "video_output_path": "", "upscale": False,
        }
        upscale_panel = MagicMock()
        upscale_panel.get_params.return_value = {"scale": 4}
        window.panels["sharp"] = panel
        window.panels["upscale"] = upscale_panel

        window._launch_sharp()

        mock_worker_cls.assert_called_once()
        args, _ = mock_worker_cls.call_args
        assert args[0] == "/in.jpg"
        assert args[1] == "/out_dir"
        instance = mock_worker_cls.return_value
        instance.start.assert_called_once()
        assert window._active_worker is instance
        window.panels["source"].set_running.assert_called_once_with(True)

    def test_sharp_video_launch_starts_sharp_video_worker(self, monkeypatch):
        window = _make_window()
        mock_worker_cls = MagicMock()
        monkeypatch.setattr(sw, "SharpVideoWorker", mock_worker_cls)
        panel = MagicMock()
        panel.get_params.return_value = {
            "mode": "video", "input_path": "", "output_path": "",
            "video_path": "/in.mp4", "video_output_path": "/out_dir", "upscale": False,
        }
        upscale_panel = MagicMock()
        upscale_panel.get_params.return_value = {"scale": 4}
        window.panels["sharp"] = panel
        window.panels["upscale"] = upscale_panel

        window._launch_sharp()

        mock_worker_cls.assert_called_once()
        args, _ = mock_worker_cls.call_args
        assert args[0] == "/in.mp4"
        assert args[1] == "/out_dir"
        instance = mock_worker_cls.return_value
        instance.start.assert_called_once()
        assert window._active_worker is instance
        window.panels["source"].set_running.assert_called_once_with(True)

    def test_splat_transform_launch_starts_splat_transform_worker(self, monkeypatch):
        window = _make_window()
        mock_worker_cls = MagicMock()
        monkeypatch.setattr(sw, "SplatTransformWorker", mock_worker_cls)
        panel = MagicMock()
        panel.input_path = _FakeLineEdit("/in.ply")
        panel.output_path = _FakeLineEdit("/out_dir")
        panel.get_params.return_value = {
            "format": "spz", "filter_nan": False, "filter_floaters": False,
            "morton": False, "harmonics": False, "decimate": 100,
        }
        window.panels["splattransform"] = panel

        window._launch_splat_transform()

        mock_worker_cls.assert_called_once_with("/in.ply", "/out_dir/in.spz", {"--overwrite": True})
        instance = mock_worker_cls.return_value
        instance.start.assert_called_once()
        assert window._active_worker is instance
        window.panels["source"].set_running.assert_called_once_with(True)

    def test_splat_transform_decimate_with_ply_output_adds_decimate_flag(self, monkeypatch):
        window = _make_window()
        mock_worker_cls = MagicMock()
        monkeypatch.setattr(sw, "SplatTransformWorker", mock_worker_cls)
        panel = MagicMock()
        panel.input_path = _FakeLineEdit("/in.ply")
        panel.output_path = _FakeLineEdit("/out_dir")
        panel.get_params.return_value = {
            "format": "ply", "filter_nan": False, "filter_floaters": False,
            "morton": False, "harmonics": False, "decimate": 50,
        }
        window.panels["splattransform"] = panel

        window._launch_splat_transform()

        mock_worker_cls.assert_called_once_with(
            "/in.ply", "/out_dir/in.ply", {"--overwrite": True, "--decimate": "50%"}
        )
        instance = mock_worker_cls.return_value
        instance.start.assert_called_once()

    def test_splat_transform_filter_floaters_adds_flag(self, monkeypatch):
        window = _make_window()
        mock_worker_cls = MagicMock()
        monkeypatch.setattr(sw, "SplatTransformWorker", mock_worker_cls)
        panel = MagicMock()
        panel.input_path = _FakeLineEdit("/in.ply")
        panel.output_path = _FakeLineEdit("/out_dir")
        panel.get_params.return_value = {
            "format": "ply", "filter_nan": False, "filter_floaters": True,
            "morton": False, "harmonics": False, "decimate": 100,
        }
        window.panels["splattransform"] = panel

        window._launch_splat_transform()

        mock_worker_cls.assert_called_once_with(
            "/in.ply", "/out_dir/in.ply", {"--overwrite": True, "--filter-floaters": True}
        )

    def test_splat_transform_decimate_with_non_ply_output_blocks_launch(self, monkeypatch):
        """splat-transform's --decimate requires a .ply output; picking spz/splat
        alongside decimation must be blocked before the worker is built, not fail
        silently at the CLI level."""
        window = _make_window()
        mock_worker_cls = MagicMock()
        monkeypatch.setattr(sw, "SplatTransformWorker", mock_worker_cls)
        monkeypatch.setattr(sw, "QMessageBox", MagicMock())
        panel = MagicMock()
        panel.input_path = _FakeLineEdit("/in.ply")
        panel.output_path = _FakeLineEdit("/out_dir")
        panel.get_params.return_value = {
            "format": "spz", "filter_nan": False, "filter_floaters": False,
            "morton": False, "harmonics": False, "decimate": 50,
        }
        window.panels["splattransform"] = panel

        window._launch_splat_transform()

        mock_worker_cls.assert_not_called()
        sw.QMessageBox.critical.assert_called_once()

    def test_upscale_launch_starts_test_worker(self, monkeypatch):
        window = _make_window()
        mock_worker_cls = MagicMock()
        monkeypatch.setattr(sw, "TestWorker", mock_worker_cls)
        panel = MagicMock()
        panel.input_path = _FakeLineEdit("/in.png")
        panel.output_path = _FakeLineEdit("/out_dir")
        panel.get_params.return_value = {"scale": 4}
        window.panels["upscale"] = panel

        window._launch_upscale()

        mock_worker_cls.assert_called_once_with("/in.png", "/out_dir", {"scale": 4})
        instance = mock_worker_cls.return_value
        instance.start.assert_called_once()
        assert window._active_worker is instance
        window.panels["source"].set_running.assert_called_once_with(True)


class TestReconstructionModeRouting:
    """The plan's "reconstruction" step does not always mean COLMAP: the
    mode choisi dans SourcePanel décide du moteur (Gsplat/Sharp/4DGS)."""

    @staticmethod
    def _window_with_source(mode):
        window = _make_window()
        window.current_pipeline_mode = mode
        window._pipeline_images_dir = None
        window._pending_upscale_params = None
        source = MagicMock()
        source.get_state.return_value = {
            "input_path": "/in_dir", "output_path": "/out_dir",
            "project_name": "proj", "fps": 5,
        }
        window.panels["source"] = source
        return window

    def test_gsplat_mode_builds_colmap_worker(self, monkeypatch):
        window = self._window_with_source("gsplat")
        sentinel = object()
        monkeypatch.setattr(sw.StudioWindow, "_build_colmap_worker", lambda self: sentinel)
        assert window._build_reconstruction_worker() is sentinel

    def test_sharp_mode_builds_sharp_worker(self, monkeypatch):
        window = self._window_with_source("sharp")
        mock_worker_cls = MagicMock()
        monkeypatch.setattr(sw, "SharpWorker", mock_worker_cls)
        panel = MagicMock()
        panel.get_params.return_value = {"mode": "video", "device": "mps"}
        window.panels["sharp"] = panel

        worker = window._build_reconstruction_worker()

        assert worker is mock_worker_cls.return_value
        args, _ = mock_worker_cls.call_args
        assert args[0] == "/in_dir"
        assert args[1] == "/out_dir"
        # The TOOLS panel video mode makes no sense inside the chain.
        assert args[2]["mode"] == "image"

    def test_fourdgs_mode_builds_fourdgs_worker(self, monkeypatch):
        window = self._window_with_source("4dgs")
        mock_worker_cls = MagicMock()
        monkeypatch.setattr(sw, "FourDGSWorker", mock_worker_cls)
        panel = MagicMock()
        panel.get_params.return_value = {
            "fps": 12, "camera_model": "OPENCV", "single_camera": True,
            "matcher_type": "sequential", "sequential_overlap": 7,
        }
        window.panels["4dgs"] = panel

        worker = window._build_reconstruction_worker()

        assert worker is mock_worker_cls.return_value
        args, kwargs = mock_worker_cls.call_args
        assert args[0] == "/in_dir"
        assert args[1].endswith("/out_dir/proj")
        assert kwargs["colmap_params"]["sequential_overlap"] == 7

    def test_missing_paths_fail_the_step(self, monkeypatch):
        window = self._window_with_source("sharp")
        window.panels["source"].get_state.return_value = {
            "input_path": "", "output_path": "", "project_name": "", "fps": 5,
        }
        window.panels["sharp"] = MagicMock()
        window._fail_pipeline_step = MagicMock()
        mock_worker_cls = MagicMock()
        monkeypatch.setattr(sw, "SharpWorker", mock_worker_cls)

        assert window._build_reconstruction_worker() is None
        mock_worker_cls.assert_not_called()
        window._fail_pipeline_step.assert_called_once()


class TestCloseEventWaitsForActiveWorker:
    """F-006 : fermer la fenêtre pendant un run ne doit pas détruire un QThread
    encore vivant (SIGABRT). ``closeEvent`` annule le worker puis attend sa fin
    (``wait``) avant d'accepter la fermeture.
    """

    class _FakeWorker:
        """Substitut minimal d'un worker (QThread) actif."""

        def __init__(self, calls):
            self._calls = calls
            self.wait_args = None

        def isRunning(self):
            return True

        def stop(self):
            self._calls.append("stop")

        def requestInterruption(self):
            self._calls.append("requestInterruption")

        def wait(self, *args):
            self.wait_args = args
            self._calls.append("wait")

    @staticmethod
    def _window(worker):
        window = sw.StudioWindow.__new__(sw.StudioWindow)
        window._active_worker = worker
        window.session_manager = MagicMock()
        window.logs_window = MagicMock()
        # Panels sans ``engine`` : rien à arrêter côté serveur, seul le
        # comportement du worker est exercé ici.
        window.panels = {"visualiser": object(), "supersplat": object()}
        return window

    @staticmethod
    def _event(calls):
        event = MagicMock()
        event.accept.side_effect = lambda: calls.append("accept")
        return event

    def test_close_event_waits_for_active_worker_before_accepting(self):
        calls = []
        worker = self._FakeWorker(calls)
        window = self._window(worker)
        event = self._event(calls)

        window.closeEvent(event)

        assert calls == ["stop", "wait", "accept"]
        assert worker.wait_args == (5000,)

    def test_close_event_without_worker_closes_normally(self):
        calls = []
        window = self._window(None)
        event = self._event(calls)

        window.closeEvent(event)

        assert calls == ["accept"]
        window.session_manager.save.assert_called_once_with(immediate=True)
