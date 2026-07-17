"""Tests pour app/core/extractor_360_engine.py — Extractor360Engine."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_engine(tmp_path, venv_exists=False, script_exists=False):
    """Crée un Extractor360Engine dont les chemins pointent dans tmp_path."""
    venv_python = tmp_path / ".venv_360" / "bin" / "python"
    if venv_exists:
        venv_python.parent.mkdir(parents=True)
        venv_python.write_text("python")

    script_path = tmp_path / "engines" / "extractor_360" / "src" / "main.py"
    if script_exists:
        script_path.parent.mkdir(parents=True)
        script_path.write_text("main")

    with patch("app.core.extractor_360_engine.resolve_project_root", return_value=tmp_path):
        with patch("app.core.extractor_360_engine.get_venv_360_python", return_value=str(venv_python)):
            from app.core.extractor_360_engine import Extractor360Engine
            engine = Extractor360Engine(logger_callback=print)

    return engine


def _create_input_output(tmp_path):
    """Crée un fichier input et un dossier output valides."""
    input_path = tmp_path / "video.mp4"
    input_path.write_bytes(b"fake_video")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return str(input_path), str(output_dir)


def _run_and_capture(engine, input_path, output_dir, params):
    """Exécute run_extraction en capturant la commande passée à _execute_command."""
    captured = {"cmd": None}

    def _fake_execute(cmd, env=None, cwd=None, line_callback=None):
        captured["cmd"] = cmd
        return 0

    with patch.object(engine, "_execute_command", side_effect=_fake_execute):
        result = engine.run_extraction(input_path, output_dir, params)

    return result, captured["cmd"]


# ─────────────────────────────────────────────────────────────────────────────
# Path resolution
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractor360EnginePaths:
    """Vérifie la résolution des chemins au démarrage du moteur."""

    def test_root_dir_resolved(self, tmp_path):
        engine = _make_engine(tmp_path)
        assert engine.root_dir == tmp_path

    def test_engines_dir_resolved(self, tmp_path):
        engine = _make_engine(tmp_path)
        assert engine.engines_dir == tmp_path / "engines"

    def test_script_path_is_src_main_py(self, tmp_path):
        engine = _make_engine(tmp_path)
        assert engine.script_path == tmp_path / "engines" / "extractor_360" / "src" / "main.py"


# ─────────────────────────────────────────────────────────────────────────────
# is_installed
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractor360EngineIsInstalled:
    """Vérifie is_installed() en fonction des fichiers présents."""

    def test_is_installed_when_venv_and_script_exist(self, tmp_path):
        engine = _make_engine(tmp_path, venv_exists=True, script_exists=True)
        assert engine.is_installed() is True

    def test_is_installed_false_when_venv_missing(self, tmp_path):
        engine = _make_engine(tmp_path, venv_exists=False, script_exists=True)
        assert engine.is_installed() is False

    def test_is_installed_false_when_script_missing(self, tmp_path):
        engine = _make_engine(tmp_path, venv_exists=True, script_exists=False)
        assert engine.is_installed() is False


# ─────────────────────────────────────────────────────────────────────────────
# Command construction
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractor360EngineRunExtraction:
    """Vérifie la construction de la ligne de commande."""

    @pytest.fixture
    def installed_engine(self, tmp_path):
        """Moteur installé avec input/output prêts."""
        engine = _make_engine(tmp_path, venv_exists=True, script_exists=True)
        input_path, output_dir = _create_input_output(tmp_path)
        return engine, input_path, output_dir

    @pytest.mark.parametrize(
        "params, flag, expected",
        [
            ({"interval": 5}, "--interval", "5"),
            ({"format": "equirectangular"}, "--format", "equirectangular"),
            ({"resolution": 2048}, "--resolution", "2048"),
            ({"camera_count": 6}, "--camera-count", "6"),
            ({"quality": 90}, "--quality", "90"),
            ({"layout": "cube"}, "--layout", "cube"),
        ],
    )
    def test_run_extraction_maps_param_to_flag(self, installed_engine, params, flag, expected):
        """Chaque paramètre est mappé sur son drapeau CLI."""
        engine, input_path, output_dir = installed_engine
        _, cmd = _run_and_capture(engine, input_path, output_dir, params)
        assert flag in cmd
        assert cmd[cmd.index(flag) + 1] == expected

    def test_run_extraction_ai_mask_flag(self, installed_engine):
        _, cmd = _run_and_capture(installed_engine[0], installed_engine[1], installed_engine[2], {"ai_mask": True})
        assert "--ai-mask" in cmd

    def test_run_extraction_ai_skip_flag(self, installed_engine):
        _, cmd = _run_and_capture(installed_engine[0], installed_engine[1], installed_engine[2], {"ai_skip": True})
        assert "--ai-skip" in cmd

    def test_run_extraction_adaptive_and_motion_threshold(self, installed_engine):
        engine, input_path, output_dir = installed_engine
        _, cmd = _run_and_capture(
            engine, input_path, output_dir, {"adaptive": True, "motion_threshold": 0.05}
        )
        assert "--adaptive" in cmd
        assert "--motion-threshold" in cmd
        assert cmd[cmd.index("--motion-threshold") + 1] == "0.05"

    def test_run_extraction_logs_command(self, installed_engine):
        engine, input_path, output_dir = installed_engine
        log_callback = MagicMock()
        engine.logger_callback = log_callback

        with patch.object(engine, "_execute_command", return_value=0):
            engine.run_extraction(input_path, output_dir, {"interval": 10}, log_callback=log_callback)

        logged = " ".join(str(arg) for call in log_callback.call_args_list for arg in call.args)
        assert "Command:" in logged
        assert "--interval" in logged

    def test_run_extraction_status_callbacks(self, installed_engine):
        engine, input_path, output_dir = installed_engine
        status_callback = MagicMock()

        with patch.object(engine, "_execute_command", return_value=0):
            engine.run_extraction(input_path, output_dir, {}, status_callback=status_callback)

        assert status_callback.call_count == 3


# ─────────────────────────────────────────────────────────────────────────────
# Security / path validation
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractor360EngineRunExtractionSecurity:
    """Vérifie le refus des chemins invalides et du moteur non installé."""

    def _bad_path_side_effect(self, p):
        return None if isinstance(p, str) and "/bad" in p else Path(p).resolve()

    def test_run_extraction_invalid_input_path_returns_false(self, tmp_path):
        engine = _make_engine(tmp_path, venv_exists=True, script_exists=True)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        log_callback = MagicMock()
        with patch.object(engine, "validate_path", side_effect=self._bad_path_side_effect):
            result = engine.run_extraction("/bad/in", str(output_dir), {}, log_callback=log_callback)

        assert result is False
        log_callback.assert_called_once()
        assert "Invalid input path" in log_callback.call_args.args[0]

    def test_run_extraction_invalid_output_path_returns_false(self, tmp_path):
        engine = _make_engine(tmp_path, venv_exists=True, script_exists=True)
        input_path = tmp_path / "video.mp4"
        input_path.write_bytes(b"fake")

        log_callback = MagicMock()
        with patch.object(engine, "validate_path", side_effect=self._bad_path_side_effect):
            result = engine.run_extraction(str(input_path), "/bad/out", {}, log_callback=log_callback)

        assert result is False
        log_callback.assert_called_once()
        assert "Invalid output directory" in log_callback.call_args.args[0]

    def test_run_extraction_not_installed_returns_false(self, tmp_path):
        engine = _make_engine(tmp_path, venv_exists=False, script_exists=False)

        log_callback = MagicMock()
        result = engine.run_extraction("/in.mp4", "/out", {}, log_callback=log_callback)

        assert result is False
        log_callback.assert_called_once()
        assert "not installed" in log_callback.call_args.args[0]


# ─────────────────────────────────────────────────────────────────────────────
# Environment isolation
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractor360EngineRunExtractionEnv:
    """Vérifie l'isolation de l'environnement d'exécution."""

    def test_run_extraction_pythonpath_isolated(self, tmp_path):
        engine = _make_engine(tmp_path, venv_exists=True, script_exists=True)
        input_path, output_dir = _create_input_output(tmp_path)

        captured = {"env": None}

        def _fake_execute(cmd, env=None, cwd=None, line_callback=None):
            captured["env"] = env
            return 0

        with patch.dict(os.environ, {"PYTHONPATH": "/some/path"}, clear=False):
            with patch.object(engine, "_execute_command", side_effect=_fake_execute):
                engine.run_extraction(input_path, output_dir, {})

        assert captured["env"] is not None
        assert "PYTHONPATH" not in captured["env"]

    def test_run_extraction_cwd_is_extractor_dir(self, tmp_path):
        engine = _make_engine(tmp_path, venv_exists=True, script_exists=True)
        input_path, output_dir = _create_input_output(tmp_path)

        captured = {"cwd": None}

        def _fake_execute(cmd, env=None, cwd=None, line_callback=None):
            captured["cwd"] = cwd
            return 0

        with patch.object(engine, "_execute_command", side_effect=_fake_execute):
            engine.run_extraction(input_path, output_dir, {})

        assert captured["cwd"] == str(engine.extractor_dir)


# ─────────────────────────────────────────────────────────────────────────────
# Progress parsing and execution flow
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractor360EngineRunExtractionProgress:
    """Vérifie le parsing de progression, l'annulation et le code retour."""

    def test_run_extraction_line_handler_extracts_percentage(self, tmp_path):
        engine = _make_engine(tmp_path, venv_exists=True, script_exists=True)
        input_path, output_dir = _create_input_output(tmp_path)
        progress_callback = MagicMock()

        def _fake_execute(cmd, env=None, cwd=None, line_callback=None):
            line_callback("[42%] Processing frame")
            return 0

        with patch.object(engine, "_execute_command", side_effect=_fake_execute):
            engine.run_extraction(input_path, output_dir, {}, progress_callback=progress_callback)

        progress_callback.assert_called_once_with(42)

    def test_run_extraction_cancel_handling(self, tmp_path):
        engine = _make_engine(tmp_path, venv_exists=True, script_exists=True)
        input_path, output_dir = _create_input_output(tmp_path)
        log_callback = MagicMock()

        with patch.object(engine, "_execute_command", return_value=0):
            result = engine.run_extraction(
                input_path,
                output_dir,
                {},
                log_callback=log_callback,
                check_cancel_callback=lambda: True,
            )

        assert result is False
        log_callback.assert_called()
        assert any("arrêté" in str(call.args[0]) for call in log_callback.call_args_list)

    def test_run_extraction_return_code_handling(self, tmp_path):
        engine = _make_engine(tmp_path, venv_exists=True, script_exists=True)
        input_path, output_dir = _create_input_output(tmp_path)

        with patch.object(engine, "_execute_command", return_value=1):
            assert engine.run_extraction(input_path, output_dir, {}) is False

        with patch.object(engine, "_execute_command", return_value=0):
            assert engine.run_extraction(input_path, output_dir, {}) is True
