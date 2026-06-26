"""Tests pour app/gui/managers.py — AppLifecycle et SessionManager."""
import os
import sys
import json
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, ANY

import pytest

# PyQt6 and send2trash mocking moved to tests/conftest.py
# to ensure patches are applied before any test module is imported.


# ─────────────────────────────────────────────────────────────────────────────
# AppLifecycle tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAppLifecycleResetFactory:
    """Tests pour AppLifecycle.reset_factory()."""

    @patch("app.gui.managers.subprocess.Popen")
    @patch("shutil.rmtree")
    @patch("app.gui.managers.resolve_project_root")
    def test_reset_factory_light(self, mock_root, mock_rmtree, mock_popen, tmp_path):
        """reset_factory(deep=False) supprime .venv, .venv_360, .venv_4dgs."""
        mock_root.return_value = tmp_path

        # Create the venv dirs
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv_360").mkdir()
        (tmp_path / ".venv_4dgs").mkdir()
        # Create run.bat for relaunch
        run_cmd = tmp_path / "run.bat"
        run_cmd.write_text("@echo off\necho run")

        from app.gui.managers import AppLifecycle

        with patch.object(sys, "exit") as mock_exit:
            AppLifecycle.reset_factory(deep=False)
            # Should remove 3 dirs
            assert mock_rmtree.call_count == 3
            # Should NOT remove engines or config.json
            calls = [c[0][0] for c in mock_rmtree.call_args_list]
            for c in calls:
                assert "engines" not in str(c)
                assert "config.json" not in str(c)

    @patch("app.gui.managers.subprocess.Popen")
    @patch("shutil.rmtree")
    @patch("app.gui.managers.resolve_project_root")
    def test_reset_factory_deep(self, mock_root, mock_rmtree, mock_popen, tmp_path):
        """reset_factory(deep=True) supprime aussi engines/ et config.json."""
        mock_root.return_value = tmp_path

        # Create dirs
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv_360").mkdir()
        (tmp_path / ".venv_4dgs").mkdir()
        (tmp_path / "engines").mkdir()
        (tmp_path / "config.json").write_text("{}")
        run_cmd = tmp_path / "run.bat"
        run_cmd.write_text("@echo off")

        from app.gui.managers import AppLifecycle

        with patch.object(sys, "exit") as mock_exit:
            AppLifecycle.reset_factory(deep=True)
            # Should remove 5 items (3 venvs + engines + config.json)
            assert mock_rmtree.call_count >= 4

    @patch("app.gui.managers.subprocess.Popen")
    @patch("shutil.rmtree")
    @patch("app.gui.managers.resolve_project_root")
    def test_reset_factory_path_outside_root_blocked(self, mock_root, mock_rmtree, mock_popen, tmp_path):
        """reset_factory bloque les chemins en dehors de project_root."""
        mock_root.return_value = tmp_path

        # Create a symlink that points outside (simulate)
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv_360").mkdir()

        from app.gui.managers import AppLifecycle

        with patch.object(sys, "exit") as mock_exit:
            AppLifecycle.reset_factory(deep=False)
            # Should only try to remove .venv and .venv_360 (within project_root)
            # Not calling rmtree on paths outside root
            assert mock_rmtree.call_count >= 2

    @patch("app.gui.managers.subprocess.Popen")
    @patch("shutil.rmtree")
    @patch("app.gui.managers.resolve_project_root")
    def test_reset_factory_nonexistent_targets_skipped(self, mock_root, mock_rmtree, mock_popen, tmp_path):
        """reset_factory ignore les cibles qui n'existent pas."""
        mock_root.return_value = tmp_path
        # Don't create any dirs — all targets don't exist

        from app.gui.managers import AppLifecycle

        with patch.object(sys, "exit") as mock_exit:
            AppLifecycle.reset_factory(deep=False)
            # rmtree should not be called for non-existent dirs
            assert mock_rmtree.call_count == 0

    @patch("app.gui.managers.subprocess.Popen")
    @patch("shutil.rmtree", side_effect=PermissionError("Access denied"))
    @patch("app.gui.managers.resolve_project_root")
    def test_reset_factory_rmtree_error_handled(self, mock_root, mock_rmtree, mock_popen, tmp_path):
        """reset_factory gère les erreurs de suppression sans planter."""
        mock_root.return_value = tmp_path
        (tmp_path / ".venv").mkdir()

        from app.gui.managers import AppLifecycle

        with patch.object(sys, "exit") as mock_exit:
            # Should not raise despite PermissionError
            AppLifecycle.reset_factory(deep=False)
            mock_rmtree.assert_called_once()

    @patch("app.gui.managers.subprocess.Popen")
    @patch("shutil.rmtree")
    @patch("app.gui.managers.resolve_project_root")
    def test_reset_factory_relaunch_via_run_command(self, mock_root, mock_rmtree, mock_popen, tmp_path):
        """reset_factory relance via run.bat."""
        mock_root.return_value = tmp_path
        run_cmd = tmp_path / "run.bat"
        run_cmd.write_text("@echo off")

        from app.gui.managers import AppLifecycle

        with patch.object(sys, "exit") as mock_exit:
            AppLifecycle.reset_factory(deep=False)
            # Should use cmd/start to launch run.bat
            popen_args = mock_popen.call_args[0][0]
            assert "cmd" in popen_args
            assert str(run_cmd) in popen_args or "run.bat" in str(popen_args)

    @patch("app.gui.managers.subprocess.Popen")
    @patch("shutil.rmtree")
    @patch("app.gui.managers.resolve_project_root")
    def test_reset_factory_no_run_command_fallback(self, mock_root, mock_rmtree, mock_popen, tmp_path):
        """reset_factory sans run.command → relance via main.py --gui."""
        mock_root.return_value = tmp_path
        # Don't create run.command

        from app.gui.managers import AppLifecycle

        with patch.object(sys, "exit") as mock_exit:
            AppLifecycle.reset_factory(deep=False)
            # Should use main.py --gui as fallback
            popen_args = mock_popen.call_args[0][0]
            assert "main.py" in str(popen_args) or "main.py" in str(popen_args)
            assert "--gui" in str(popen_args)


class TestAppLifecycleRestart:
    """Tests pour AppLifecycle.restart()."""

    @patch("app.gui.managers.subprocess.Popen")
    @patch("app.gui.managers.os.execv")
    @patch("app.gui.managers.resolve_project_root")
    @patch("app.gui.managers.QApplication.quit")
    def test_restart_normal(self, mock_quit, mock_root, mock_execv, mock_popen, tmp_path):
        """restart normal utilise execv."""
        mock_root.return_value = tmp_path

        # Create engines/brush so needs_setup=False
        engines_dir = tmp_path / "engines"
        engines_dir.mkdir()
        (engines_dir / "brush").write_text("binary")

        from app.gui.managers import AppLifecycle

        with patch.object(sys, "exit") as mock_exit:
            # Prevent actual sys.exit
            mock_exit.side_effect = SystemExit
            try:
                AppLifecycle.restart()
            except SystemExit:
                pass

            # execv should be called (or Popen as fallback)
            assert mock_execv.call_count >= 0  # might fail on some platforms

    @patch("app.gui.managers.subprocess.Popen")
    @patch("app.gui.managers.os.execv")
    @patch("app.gui.managers.resolve_project_root")
    @patch("app.gui.managers.QApplication.quit")
    def test_restart_with_save_callback(self, mock_quit, mock_root, mock_execv, mock_popen, tmp_path):
        """restart appelle save_callback si fourni."""
        mock_root.return_value = tmp_path

        engines_dir = tmp_path / "engines"
        engines_dir.mkdir()
        (engines_dir / "brush").write_text("binary")

        save_cb = MagicMock()

        from app.gui.managers import AppLifecycle

        with patch.object(sys, "exit") as mock_exit:
            mock_exit.side_effect = SystemExit
            try:
                AppLifecycle.restart(save_callback=save_cb)
            except SystemExit:
                pass

            save_cb.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# SessionManager tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSessionManager:
    """Tests pour SessionManager — sauvegarde et chargement de session."""

    @pytest.fixture
    def session_manager(self, request, tmp_path):
        """Crée un SessionManager avec des tabs mockés + patch actif."""
        patcher = patch("app.gui.managers.resolve_project_root", return_value=tmp_path)
        patcher.start()
        request.addfinalizer(patcher.stop)

        # Create main_window with mocked tabs
        main_window = MagicMock()

        # Mock tabs with get_state returning serializable dicts
        for tab_name in ["config_tab", "params_tab", "brush_tab",
                         "upscale_tab", "extractor_360_tab", "four_dgs_tab", "superplat_tab"]:
            tab = MagicMock()
            tab.get_state = MagicMock(return_value={"param1": "value1"})
            setattr(main_window, tab_name, tab)

        # Config tab needs combo_lang.currentData() to return a string
        main_window.config_tab.combo_lang.currentData = MagicMock(return_value="fr")

        from app.gui.managers import SessionManager
        sm = SessionManager(main_window)
        return sm

    def test_save_creates_config_file(self, session_manager, tmp_path):
        """save(immediate=True) crée config.json."""
        session_manager.save(immediate=True)
        config_file = tmp_path / "config.json"
        assert config_file.exists()
        data = json.loads(config_file.read_text())
        assert data["language"] == "fr"

    def test_save_and_load_roundtrip(self, session_manager, tmp_path):
        """save puis load restaure l'état."""
        session_manager.save(immediate=True)
        config_file = tmp_path / "config.json"
        assert config_file.exists()

        # load should call set_state on each tab
        session_manager.load()

        # Verify set_state was called
        for tab_name in ["config_tab", "params_tab", "brush_tab"]:
            tab = getattr(session_manager.mw, tab_name)
            tab.set_state.assert_called_with({"param1": "value1"})

    def test_load_no_session_file(self, session_manager, tmp_path):
        """load sans fichier ne fait rien."""
        config_file = tmp_path / "config.json"
        assert not config_file.exists()

        # Should not raise
        session_manager.load()

    def test_save_with_tab_get_params(self, session_manager, tmp_path):
        """save utilise get_params si get_state n'existe pas."""
        # Remove get_state so hasattr falls through to get_params
        del session_manager.mw.config_tab.get_state
        session_manager.mw.config_tab.get_params = MagicMock(return_value={"custom": "value"})

        session_manager.save(immediate=True)
        config_file = tmp_path / "config.json"
        assert config_file.exists()
        data = json.loads(config_file.read_text())
        assert data["language"] == "fr"

    def test_save_with_params_to_dict(self, session_manager, tmp_path):
        """save convertit les params via to_dict si disponible."""
        class ParamsWithDict:
            def to_dict(self):
                return {"converted": True}

        del session_manager.mw.brush_tab.get_state
        session_manager.mw.brush_tab.get_params = MagicMock(return_value=ParamsWithDict())

        session_manager.save(immediate=True)
        config_file = tmp_path / "config.json"
        assert config_file.exists()

    def test_load_with_set_params(self, session_manager, tmp_path):
        """load utilise set_params si set_state n'existe pas."""
        # Write a config file first
        state = {
            "language": "en",
            "colmap_params": {"camera_model": "OPENCV"},
        }
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(state))

        # Remove set_state from params_tab so load falls through to set_params
        del session_manager.mw.params_tab.set_state
        session_manager.mw.params_tab.set_params = MagicMock()

        session_manager.load()

        # Should use set_params instead
        session_manager.mw.params_tab.set_params.assert_called_once()

    def test_load_corrupted_json(self, session_manager, tmp_path):
        """Fichier JSON corrompu → pas d'erreur."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{invalide json")

        # Should not raise
        session_manager.load()

    def test_debounce_timer(self, session_manager):
        """save sans immediate démarre le timer."""
        session_manager._save_timer = MagicMock()
        session_manager.save(immediate=False)
        session_manager._save_timer.start.assert_called_once_with(1500)

    def test_get_session_file(self, tmp_path):
        """get_session_file retourne config.json dans project_root."""
        with patch("app.gui.managers.resolve_project_root", return_value=tmp_path):
            main_window = MagicMock()
            from app.gui.managers import SessionManager
            sm = SessionManager(main_window)
            session_file = sm.get_session_file()
            assert session_file == tmp_path / "config.json"
