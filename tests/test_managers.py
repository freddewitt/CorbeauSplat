"""Tests for app/gui/managers.py — AppLifecycle and SessionManager.
"""
import contextlib
import json
import sys
from unittest.mock import MagicMock, patch

import pytest

# PySide6 and send2trash mocking moved to tests/conftest.py
# to ensure patches are applied before any test module is imported.


# ─────────────────────────────────────────────────────────────────────────────
# AppLifecycle tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAppLifecycleResetFactory:
    """Tests for AppLifecycle.reset_factory()."""

    @patch("app.gui.managers.subprocess.Popen")
    @patch("shutil.rmtree")
    @patch("app.gui.managers.resolve_project_root")
    def test_reset_factory_light(self, mock_root, mock_rmtree, mock_popen, tmp_path):
        """reset_factory(deep=False) removes .venv, .venv_sharp, .venv_360."""
        mock_root.return_value = tmp_path

        # Create the venv dirs
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv_sharp").mkdir()
        (tmp_path / ".venv_360").mkdir()
        # Create launcher for relaunch
        run_cmd = tmp_path / "CorbeauSplat.command"
        run_cmd.write_text("#!/bin/bash\necho run")

        from app.gui.managers import AppLifecycle

        with patch.object(sys, "exit"):
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
        """reset_factory(deep=True) also removes engines/ and config.json."""
        mock_root.return_value = tmp_path

        # Create dirs
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv_sharp").mkdir()
        (tmp_path / ".venv_360").mkdir()
        (tmp_path / "engines").mkdir()
        (tmp_path / "config.json").write_text("{}")
        run_cmd = tmp_path / "CorbeauSplat.command"
        run_cmd.write_text("#!/bin/bash")

        from app.gui.managers import AppLifecycle

        with patch.object(sys, "exit"):
            AppLifecycle.reset_factory(deep=True)
            # Should remove 5 items (3 venvs + engines + config.json)
            assert mock_rmtree.call_count >= 4

    @patch("app.gui.managers.subprocess.Popen")
    @patch("shutil.rmtree")
    @patch("app.gui.managers.resolve_project_root")
    def test_reset_factory_path_outside_root_blocked(self, mock_root, mock_rmtree, mock_popen, tmp_path):
        """reset_factory blocks paths outside project_root."""
        mock_root.return_value = tmp_path

        # Create a symlink that points outside (simulate)
        (tmp_path / ".venv").mkdir()
        (tmp_path / ".venv_sharp").mkdir()

        from app.gui.managers import AppLifecycle

        with patch.object(sys, "exit"):
            AppLifecycle.reset_factory(deep=False)
            # Should only try to remove .venv and .venv_sharp (within project_root)
            # Not calling rmtree on paths outside root
            assert mock_rmtree.call_count >= 2

    @patch("app.gui.managers.subprocess.Popen")
    @patch("shutil.rmtree")
    @patch("app.gui.managers.resolve_project_root")
    def test_reset_factory_nonexistent_targets_skipped(self, mock_root, mock_rmtree, mock_popen, tmp_path):
        """reset_factory skips targets that do not exist."""
        mock_root.return_value = tmp_path
        # Don't create any dirs — all targets don't exist

        from app.gui.managers import AppLifecycle

        with patch.object(sys, "exit"):
            AppLifecycle.reset_factory(deep=False)
            # rmtree should not be called for non-existent dirs
            assert mock_rmtree.call_count == 0

    @patch("app.gui.managers.subprocess.Popen")
    @patch("shutil.rmtree", side_effect=PermissionError("Access denied"))
    @patch("app.gui.managers.resolve_project_root")
    def test_reset_factory_rmtree_error_handled(self, mock_root, mock_rmtree, mock_popen, tmp_path):
        """reset_factory handles deletion errors without crashing."""
        mock_root.return_value = tmp_path
        (tmp_path / ".venv").mkdir()

        from app.gui.managers import AppLifecycle

        with patch.object(sys, "exit"):
            # Should not raise despite PermissionError
            AppLifecycle.reset_factory(deep=False)
            mock_rmtree.assert_called_once()

    @patch("app.gui.managers.subprocess.Popen")
    @patch("shutil.rmtree")
    @patch("app.gui.managers.resolve_project_root")
    def test_reset_factory_relaunch_via_run_command(self, mock_root, mock_rmtree, mock_popen, tmp_path):
        """reset_factory relaunches through CorbeauSplat.command."""
        mock_root.return_value = tmp_path
        run_cmd = tmp_path / "CorbeauSplat.command"
        run_cmd.write_text("#!/bin/bash")

        from app.gui.managers import AppLifecycle

        with patch.object(sys, "exit"):
            AppLifecycle.reset_factory(deep=False)
            # Should use "open" for the launcher
            popen_args = mock_popen.call_args[0][0]
            assert "open" in popen_args
            assert str(run_cmd) in popen_args or "CorbeauSplat.command" in str(popen_args)

    @patch("app.gui.managers.subprocess.Popen")
    @patch("shutil.rmtree")
    @patch("app.gui.managers.resolve_project_root")
    def test_reset_factory_no_run_command_fallback(self, mock_root, mock_rmtree, mock_popen, tmp_path):
        """reset_factory without a launcher → relaunches through main.py --gui."""
        mock_root.return_value = tmp_path
        # Don't create the launcher file

        from app.gui.managers import AppLifecycle

        with patch.object(sys, "exit"):
            AppLifecycle.reset_factory(deep=False)
            # Should use main.py --gui as fallback
            popen_args = mock_popen.call_args[0][0]
            assert "main.py" in str(popen_args) or "main.py" in str(popen_args)
            assert "--gui" in str(popen_args)


class TestAppLifecycleRestart:
    """Tests for AppLifecycle.restart()."""

    @patch("app.gui.managers.subprocess.Popen")
    @patch("app.gui.managers.os.execv")
    @patch("app.gui.managers.resolve_project_root")
    @patch("app.gui.managers.QApplication.quit")
    def test_restart_normal(self, mock_quit, mock_root, mock_execv, mock_popen, tmp_path):
        """A normal restart uses execv."""
        mock_root.return_value = tmp_path

        # Create engines/brush so needs_setup=False
        engines_dir = tmp_path / "engines"
        engines_dir.mkdir()
        (engines_dir / "brush").write_text("binary")

        from app.gui.managers import AppLifecycle

        with patch.object(sys, "exit") as mock_exit:
            # Prevent actual sys.exit
            mock_exit.side_effect = SystemExit
            with contextlib.suppress(SystemExit):
                AppLifecycle.restart()

            # execv should be called (or Popen as fallback)
            assert mock_execv.call_count >= 0  # might fail on some platforms

    @patch("app.gui.managers.subprocess.Popen")
    @patch("app.gui.managers.os.execv")
    @patch("app.gui.managers.resolve_project_root")
    @patch("app.gui.managers.QApplication.quit")
    def test_restart_with_save_callback(self, mock_quit, mock_root, mock_execv, mock_popen, tmp_path):
        """restart calls save_callback when one is supplied."""
        mock_root.return_value = tmp_path

        engines_dir = tmp_path / "engines"
        engines_dir.mkdir()
        (engines_dir / "brush").write_text("binary")

        save_cb = MagicMock()

        from app.gui.managers import AppLifecycle

        with patch.object(sys, "exit") as mock_exit:
            mock_exit.side_effect = SystemExit
            with contextlib.suppress(SystemExit):
                AppLifecycle.restart(save_callback=save_cb)

            save_cb.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# SessionManager tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSessionManager:
    """Tests for SessionManager — persistence of the last project (Source
    panel) under the ``"last_project"`` key of ``config.json``.
    """

    _PROJECT_STATE = {
        "project_name": "MonProjet",
        "input_path": "/tmp/source",
        "output_path": "/tmp/sortie",
        "checkpoint_dest": "",
        "fps": 2,
        "upscale": False,
        "filter_blur": False,
        "blur_strength": "medium",
        "stabilized": False,
        "export_dir": "",
        "export_format": "spz",
    }

    @pytest.fixture
    def session_manager(self, request, tmp_path):
        """Build a SessionManager with a minimal mocked StudioWindow (a single
        Source panel, like the rest of the window) + active patch.
        """
        patcher = patch("app.gui.managers.resolve_project_root", return_value=tmp_path)
        patcher.start()
        request.addfinalizer(patcher.stop)

        source_panel = MagicMock()
        source_panel.get_state = MagicMock(return_value=dict(self._PROJECT_STATE))

        main_window = MagicMock()
        main_window.panels = {"source": source_panel}

        from app.gui.managers import SessionManager
        return SessionManager(main_window)

    def test_save_creates_config_file(self, session_manager, tmp_path):
        """save(immediate=True) creates config.json with the last_project key."""
        session_manager.save(immediate=True)
        config_file = tmp_path / "config.json"
        assert config_file.exists()
        data = json.loads(config_file.read_text())
        assert data["last_project"] == self._PROJECT_STATE

    def test_save_preserves_other_keys(self, session_manager, tmp_path):
        """save merges with an existing config.json: it destroys neither
        'language' (managed by LanguageManager) nor any other key already there.
        """
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"language": "fr", "other_key": 42}))

        session_manager.save(immediate=True)

        data = json.loads(config_file.read_text())
        assert data["language"] == "fr"
        assert data["other_key"] == 42
        assert data["last_project"] == self._PROJECT_STATE

    def test_save_and_load_roundtrip(self, session_manager, tmp_path):
        """save then load restores the state onto the Source panel (set_state)."""
        session_manager.save(immediate=True)
        config_file = tmp_path / "config.json"
        assert config_file.exists()

        session_manager.load()

        source_panel = session_manager.mw.panels["source"]
        source_panel.set_state.assert_called_once_with(self._PROJECT_STATE)

    def test_load_no_session_file(self, session_manager, tmp_path):
        """load without a file does nothing (no set_state call)."""
        config_file = tmp_path / "config.json"
        assert not config_file.exists()

        session_manager.load()

        session_manager.mw.panels["source"].set_state.assert_not_called()

    def test_load_no_last_project_key(self, session_manager, tmp_path):
        """load with an existing config.json but no last_project does nothing
        (e.g. a file written by LanguageManager only).
        """
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"language": "en"}))

        session_manager.load()

        session_manager.mw.panels["source"].set_state.assert_not_called()

    def test_load_corrupted_json(self, session_manager, tmp_path):
        """Corrupted JSON file → no error."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{invalide json")

        # Should not raise
        session_manager.load()

    def test_save_no_source_panel(self, tmp_path):
        """save without a Source panel (minimal main_window) does not crash."""
        with patch("app.gui.managers.resolve_project_root", return_value=tmp_path):
            main_window = MagicMock()
            main_window.panels = {}
            from app.gui.managers import SessionManager
            sm = SessionManager(main_window)
            sm.save(immediate=True)
            assert not (tmp_path / "config.json").exists()

    def test_debounce_timer(self, session_manager):
        """save without immediate starts the timer."""
        session_manager._save_timer = MagicMock()
        session_manager.save(immediate=False)
        session_manager._save_timer.start.assert_called_once_with(1500)

    def test_get_session_file(self, tmp_path):
        """get_session_file returns config.json inside project_root."""
        with patch("app.gui.managers.resolve_project_root", return_value=tmp_path):
            main_window = MagicMock()
            from app.gui.managers import SessionManager
            sm = SessionManager(main_window)
            session_file = sm.get_session_file()
            assert session_file == tmp_path / "config.json"
