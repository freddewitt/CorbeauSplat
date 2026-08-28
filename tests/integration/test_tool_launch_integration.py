"""Tests d'intégration : chaque module OUTILS déclenche le bon worker via
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

# StudioWindow(QMainWindow) doit rester une vraie classe Python instanciable
# via __new__ (bypass __init__, comme les workers testés ailleurs) : sous le
# mock PySide6 de la session, QtWidgets est un MagicMock générique dont les
# attributs ne sont pas des types utilisables comme classe de base. On ne
# remplace que QMainWindow (seule base utilisée), avant le premier import de
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
    """StudioWindow sans passer par __init__ (pas de vrais widgets Qt requis)."""
    window = sw.StudioWindow.__new__(sw.StudioWindow)
    window._active_worker = None
    window.activity_bar = MagicMock()
    window.logs_window = MagicMock()
    # _start_tool_worker() nomme l'étape courante dans la barre d'activité à
    # partir de la page affichée (PageRegistry.current).
    window.nav = MagicMock()
    window.nav.current = "upscale"
    # SourcePanel (ex-topbar) porte désormais le bouton Lancer/Annuler unique ;
    # _start_tool_worker() bascule son état via set_running().
    window.panels = {"source": MagicMock()}
    return window


class TestToolLaunchOrchestration:
    """Chaque module OUTILS passe par le même chemin : bouton local →
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
        }
        upscale_panel = MagicMock()
        upscale_panel.get_params.return_value = {"scale": 4}
        window.panels["4dgs"] = panel
        window.panels["upscale"] = upscale_panel

        window._launch_fourdgs()

        mock_worker_cls.assert_called_once_with(
            "/videos_dir", "/out_dir", 5,
            upscale_params={"scale": 4, "active": False},
        )
        instance = mock_worker_cls.return_value
        instance.start.assert_called_once()
        assert window._active_worker is instance
        window.panels["source"].set_running.assert_called_once_with(True)

    def test_fourdgs_colmap_only_launch_starts_fourdgs_worker_without_videos(self, monkeypatch):
        """Case « Reconstruction COLMAP seulement » cochée : ignore le champ
        Source même rempli, FourDGSWorker reçoit videos_dir=None (mode COLMAP
        seul, cf. ancien FourDGSTab.run_colmap_only)."""
        window = _make_window()
        mock_worker_cls = MagicMock()
        monkeypatch.setattr(sw, "FourDGSWorker", mock_worker_cls)
        panel = MagicMock()
        panel.get_params.return_value = {
            "input_path": "/videos_dir", "output_path": "/out_dir", "fps": 5,
            "upscale": False, "colmap_only": True,
        }
        upscale_panel = MagicMock()
        upscale_panel.get_params.return_value = {"scale": 4}
        window.panels["4dgs"] = panel
        window.panels["upscale"] = upscale_panel

        window._launch_fourdgs()

        mock_worker_cls.assert_called_once_with(
            None, "/out_dir", 5,
            upscale_params={"scale": 4, "active": False},
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
            "format": "spz", "filter_nan": False, "morton": False,
            "harmonics": False, "decimate": 100,
        }
        window.panels["splattransform"] = panel

        window._launch_splat_transform()

        mock_worker_cls.assert_called_once_with("/in.ply", "/out_dir/in.spz", {"--overwrite": True})
        instance = mock_worker_cls.return_value
        instance.start.assert_called_once()
        assert window._active_worker is instance
        window.panels["source"].set_running.assert_called_once_with(True)

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
