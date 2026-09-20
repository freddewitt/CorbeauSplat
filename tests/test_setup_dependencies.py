"""Tests for app.scripts.setup_dependencies.py and app/core/system.py.
The patches now target app.scripts.installers.* where the functions are defined,
while the imports stay from app.scripts.setup_dependencies (re-exports).
"""
import json
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Tests for checksum_verifier (used by setup_dependencies)
# ─────────────────────────────────────────────────────────────────────────────

class TestChecksumVerifier:
    """Tests for the checksum verification functions."""

    def test_load_expected_checksums_success(self, tmp_path):
        """load_expected_checksums returns the JSON dict."""
        # Patch the CHECKSUMS_PATH to point to a temp file
        checksums_file = tmp_path / "checksums.json"
        checksums_file.write_text(json.dumps({"darwin_brush": "abc123"}))

        with patch("app.scripts.checksum_verifier.CHECKSUMS_PATH", checksums_file):
            from app.scripts.checksum_verifier import load_expected_checksums
            result = load_expected_checksums()
            assert result == {"darwin_brush": "abc123"}

    @patch("app.scripts.checksum_verifier.CHECKSUMS_PATH")
    def test_load_expected_checksums_not_found(self, mock_path):
        """load_expected_checksums without a file → empty dict."""
        mock_path.exists.return_value = False

        from app.scripts.checksum_verifier import load_expected_checksums
        result = load_expected_checksums()
        assert result == {}

    def test_load_expected_checksums_invalid_json(self, tmp_path):
        """load_expected_checksums with invalid JSON → empty dict."""
        checksums_file = tmp_path / "checksums.json"
        checksums_file.write_text("not json")

        with patch("app.scripts.checksum_verifier.CHECKSUMS_PATH", checksums_file):
            from app.scripts.checksum_verifier import load_expected_checksums
            result = load_expected_checksums()
            assert result == {}


# ─────────────────────────────────────────────────────────────────────────────
# Tests for get_brush_build_mode
# ─────────────────────────────────────────────────────────────────────────────

class TestGetBrushBuildMode:
    """Tests for system.get_brush_build_mode()."""

    @patch("app.core.system.resolve_project_root")
    def test_source_mode_detected(self, mock_root, tmp_path):
        """Version file with 'source' → returns 'source'."""
        engines_dir = tmp_path / "engines"
        engines_dir.mkdir(parents=True)
        version_file = engines_dir / "brush.version"
        version_file.write_text("abc12345-source")
        mock_root.return_value = tmp_path

        from app.core.system import get_brush_build_mode
        assert get_brush_build_mode() == "source"

    @patch("app.core.system.resolve_project_root")
    def test_release_mode_detected(self, mock_root, tmp_path):
        """Version file without 'source' → returns 'release'."""
        engines_dir = tmp_path / "engines"
        engines_dir.mkdir(parents=True)
        version_file = engines_dir / "brush.version"
        version_file.write_text("v0.3.0")
        mock_root.return_value = tmp_path

        from app.core.system import get_brush_build_mode
        assert get_brush_build_mode() == "release"

    @patch("app.core.system.resolve_binary", return_value=None)
    @patch("app.core.system.resolve_project_root")
    def test_no_version_file_and_no_binary(self, mock_root, _mock_bin, tmp_path):
        """No version file and no binary to ask → last-resort 'release'."""
        mock_root.return_value = tmp_path

        import app.core.system as system
        system._BRUSH_PROBED_MODE = None
        assert system.get_brush_build_mode() == "release"

    @patch("app.core.system.resolve_binary", return_value="/usr/local/bin/brush")
    @patch("app.core.system.resolve_project_root")
    def test_source_build_detected_by_probing_the_binary(self, mock_root, _mock_bin, tmp_path):
        """Without a version file, the binary is asked instead of guessed.

        Guessing 'release' here handed a source build `--total-steps`, which it
        rejects, so the training died immediately (audit I15).
        """
        mock_root.return_value = tmp_path

        import app.core.system as system
        system._BRUSH_PROBED_MODE = None
        completed = subprocess.CompletedProcess([], 0, stdout="--total-train-iters <N>", stderr="")
        with patch("subprocess.run", return_value=completed):
            assert system.get_brush_build_mode() == "source"

    @patch("app.core.system.resolve_binary", return_value="/usr/local/bin/brush")
    @patch("app.core.system.resolve_project_root")
    def test_probe_result_is_cached(self, mock_root, _mock_bin, tmp_path):
        """The probe spawns a process, so it must run once per session."""
        mock_root.return_value = tmp_path

        import app.core.system as system
        system._BRUSH_PROBED_MODE = None
        completed = subprocess.CompletedProcess([], 0, stdout="--total-steps <N>", stderr="")
        with patch("subprocess.run", return_value=completed) as mock_run:
            system.get_brush_build_mode()
            system.get_brush_build_mode()
        assert mock_run.call_count == 1

    @patch("app.core.system.resolve_project_root")
    def test_version_file_wins_over_probing(self, mock_root, tmp_path):
        """Evidence written at install time is preferred; no process is spawned."""
        engines_dir = tmp_path / "engines"
        engines_dir.mkdir(parents=True)
        (engines_dir / "brush.version").write_text("abc12345-source")
        mock_root.return_value = tmp_path

        import app.core.system as system
        system._BRUSH_PROBED_MODE = None
        with patch("subprocess.run") as mock_run:
            assert system.get_brush_build_mode() == "source"
        mock_run.assert_not_called()

    @patch("app.core.system.resolve_project_root")
    def test_empty_version_file(self, mock_root, tmp_path):
        """Empty version file → returns 'release'."""
        engines_dir = tmp_path / "engines"
        engines_dir.mkdir(parents=True)
        version_file = engines_dir / "brush.version"
        version_file.write_text("")
        mock_root.return_value = tmp_path

        from app.core.system import get_brush_build_mode
        assert get_brush_build_mode() == "release"


# ─────────────────────────────────────────────────────────────────────────────
# Tests for system.check_dependencies
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckDependencies:
    """Tests for system.check_dependencies()."""

    @patch("app.core.system.resolve_binary")
    def test_all_dependencies_present(self, mock_resolve_binary):
        """Every dependency present → empty list."""
        mock_resolve_binary.side_effect = lambda x: x  # found
        # send2trash is already in sys.modules (possibly mocked), patch find_spec
        import importlib.util
        with patch.object(importlib.util, 'find_spec', return_value=True):
            from app.core.system import check_dependencies
            missing = check_dependencies()
            assert missing == []

    @patch("app.core.system.resolve_binary")
    def test_some_missing(self, mock_resolve_binary):
        """Missing dependencies → non-empty list."""
        mock_resolve_binary.side_effect = lambda x: None  # nothing found
        import importlib.util
        with patch.object(importlib.util, 'find_spec', return_value=None):
            from app.core.system import check_dependencies
            missing = check_dependencies()
            assert "ffmpeg" in missing
            assert "colmap" in missing
            assert "send2trash" in missing

    @patch("app.core.system.resolve_binary")
    def test_partial_missing(self, mock_resolve_binary):
        """Some dependencies missing."""
        def resolve_side_effect(name):
            if name == "ffmpeg":
                return "/usr/local/bin/ffmpeg"
            return None

        mock_resolve_binary.side_effect = resolve_side_effect
        import importlib.util
        with patch.object(importlib.util, 'find_spec', return_value=True):  # send2trash present
            from app.core.system import check_dependencies
            missing = check_dependencies()
            assert "ffmpeg" not in missing
            assert "colmap" in missing
            assert "send2trash" not in missing

    @patch("app.core.system.resolve_binary")
    def test_feature_binaries_are_checked_and_labelled(self, mock_resolve_binary):
        """brush/glomap/upscayl-bin/npx are reported, each naming what it blocks.

        Until the 2026-09-15 audit none of the four was checked at all, so a
        missing Brush only surfaced once a training had been launched.
        """
        mock_resolve_binary.side_effect = lambda name: None
        import importlib.util
        with patch.object(importlib.util, 'find_spec', return_value=True):
            from app.core.system import check_dependencies
            missing = check_dependencies()

        assert "brush (entraînement)" in missing
        assert "glomap (mapper Glomap)" in missing
        assert "upscayl-bin (upscale)" in missing
        assert "npx (visualisation SuperSplat)" in missing

    @patch("app.core.system.resolve_binary")
    def test_feature_binaries_absent_from_list_when_present(self, mock_resolve_binary):
        """A tool that resolves is not reported, labelled or otherwise."""
        mock_resolve_binary.side_effect = lambda name: f"/usr/local/bin/{name}"
        import importlib.util
        with patch.object(importlib.util, 'find_spec', return_value=True):
            from app.core.system import check_dependencies
            missing = check_dependencies()

        assert missing == []


# ─────────────────────────────────────────────────────────────────────────────
# Tests for setup_dependencies utility functions
# ─────────────────────────────────────────────────────────────────────────────

class TestSetupDependenciesUtils:
    """Tests for the utility functions of setup_dependencies.py."""

    def test_relax_requirements(self, tmp_path):
        """relax_requirements turns torch== into torch>=."""
        from app.scripts.setup_dependencies import relax_requirements

        src = tmp_path / "requirements.txt"
        dst = tmp_path / "requirements_loose.txt"
        src.write_text("torch==2.0.1\ntorchvision==0.15.2\nnumpy>=1.26\n")

        relax_requirements(str(src), str(dst))

        content = dst.read_text()
        assert "torch>=2.0.1" in content
        assert "torchvision>=0.15.2" in content
        assert "numpy>=1.26" in content

    def test_check_cargo(self):
        """check_cargo checks that cargo is present."""
        with patch("app.scripts.installers.tools.shutil.which") as mock_which:
            mock_which.return_value = "/usr/local/bin/cargo"
            from app.scripts.installers.tools import check_cargo
            assert check_cargo() is True

    def test_check_cargo_not_found(self):
        """check_cargo returns False when cargo is missing."""
        with patch("app.scripts.installers.tools.shutil.which") as mock_which:
            mock_which.return_value = None
            from app.scripts.installers.tools import check_cargo
            assert check_cargo() is False

    def test_check_brew(self):
        """check_brew checks that brew is present."""
        with patch("app.scripts.installers.tools.shutil.which") as mock_which:
            mock_which.return_value = "/opt/homebrew/bin/brew"
            from app.scripts.installers.tools import check_brew
            assert check_brew() is True

    def test_check_node(self):
        """check_node checks node and npm."""
        with patch("app.scripts.installers.tools.shutil.which") as mock_which:
            mock_which.side_effect = lambda x: f"/usr/local/bin/{x}" if x in ("node", "npm") else None
            from app.scripts.installers.tools import check_node
            assert check_node() is True

    def test_check_node_missing_npm(self):
        """check_node returns False when npm is missing."""
        with patch("app.scripts.installers.tools.shutil.which") as mock_which:
            def which_side_effect(name):
                if name == "node":
                    return "/usr/local/bin/node"
                return None
            mock_which.side_effect = which_side_effect
            from app.scripts.installers.tools import check_node
            assert check_node() is False

    def test_check_cmake_ninja(self):
        """check_cmake_ninja checks cmake and ninja."""
        with patch("app.scripts.installers.tools.shutil.which") as mock_which:
            mock_which.side_effect = lambda x: f"/usr/local/bin/{x}"
            from app.scripts.installers.tools import check_cmake_ninja
            assert check_cmake_ninja() is True

    def test_check_xcode_tools_present(self):
        """check_xcode_tools returns True when xcode-select -p succeeds."""
        import sys as _sys
        if _sys.platform != "darwin":
            pytest.skip("xcode-select test only relevant on macOS")
        with patch("app.scripts.installers.tools.subprocess.check_call") as mock_check:
            from app.scripts.installers.tools import check_xcode_tools
            assert check_xcode_tools() is True
            mock_check.assert_called_once_with(
                ["xcode-select", "-p"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def test_check_xcode_tools_missing(self):
        """check_xcode_tools returns False when xcode-select fails."""
        import sys as _sys
        if _sys.platform != "darwin":
            pytest.skip("xcode-select test only relevant on macOS")
        with patch("app.scripts.installers.tools.subprocess.check_call") as mock_check:
            mock_check.side_effect = subprocess.CalledProcessError(1, "xcode-select")
            from app.scripts.installers.tools import check_xcode_tools
            assert check_xcode_tools() is False

    def test_get_remote_version(self):
        """get_remote_version uses git ls-remote."""
        with patch("app.scripts.installers.tools.subprocess.check_output") as mock_check:
            mock_check.return_value = "abc123def\tHEAD\n"
            from app.scripts.installers.tools import get_remote_version
            result = get_remote_version("https://github.com/test/repo.git")
            assert result == "abc123def"

    def test_get_remote_version_failure(self):
        """get_remote_version returns None on error."""
        with patch("app.scripts.installers.tools.subprocess.check_output") as mock_check:
            mock_check.side_effect = Exception("git error")
            from app.scripts.installers.tools import get_remote_version
            result = get_remote_version("https://github.com/test/repo.git")
            assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests for EngineDependency
# ─────────────────────────────────────────────────────────────────────────────

class TestEngineDependency:
    """Tests for the EngineDependency class."""

    def test_is_installed(self, tmp_path):
        """is_installed checks that the binary exists."""
        from app.scripts.installers.base import EngineDependency

        with patch("app.scripts.installers.base.resolve_project_root", return_value=tmp_path):
            dep = EngineDependency("test_engine", bin_name="test_bin")
            # Create the binary
            dep.bin_path.parent.mkdir(parents=True, exist_ok=True)
            dep.bin_path.write_text("binary")
            assert dep.is_installed() is True

    def test_is_not_installed(self, tmp_path):
        """is_installed returns False when the binary is missing."""
        from app.scripts.installers.base import EngineDependency

        with patch("app.scripts.installers.base.resolve_project_root", return_value=tmp_path):
            dep = EngineDependency("test_engine", bin_name="test_bin")
            assert dep.is_installed() is False

    def test_save_and_get_local_version(self, tmp_path):
        """save_local_version then get_local_version."""
        from app.scripts.installers.base import EngineDependency

        with patch("app.scripts.installers.base.resolve_project_root", return_value=tmp_path):
            dep = EngineDependency("test_engine", bin_name="test_bin")
            dep.save_local_version("v1.0.0")
            assert dep.get_local_version() == "v1.0.0"

    def test_get_local_version_missing(self, tmp_path):
        """get_local_version without a file → empty string."""
        from app.scripts.installers.base import EngineDependency

        with patch("app.scripts.installers.base.resolve_project_root", return_value=tmp_path):
            dep = EngineDependency("test_engine", bin_name="test_bin")
            assert dep.get_local_version() == ""

    def test_is_enabled_in_config(self, tmp_path):
        """is_enabled_in_config uses the config."""
        from app.scripts.installers.base import EngineDependency

        dep = EngineDependency("test_engine", bin_name="test_bin")
        config = {"test_engine_enabled": True}
        assert dep.is_enabled_in_config(config) is True

    def test_is_enabled_in_config_default(self, tmp_path):
        """is_enabled_in_config returns True by default."""
        from app.scripts.installers.base import EngineDependency

        dep = EngineDependency("test_engine", bin_name="test_bin")
        config = {}
        assert dep.is_enabled_in_config(config) is True

    def test_uninstall(self, tmp_path):
        """uninstall removes target_dir and version_file."""
        from app.scripts.installers.base import EngineDependency

        with patch("app.scripts.installers.base.resolve_project_root", return_value=tmp_path):
            dep = EngineDependency("test_engine", bin_name="test_bin")

            # Create files
            dep.target_dir.mkdir(parents=True)
            (dep.target_dir / "somefile").write_text("data")
            dep.save_local_version("v1.0")

            assert dep.target_dir.exists()
            assert dep.version_file.exists()

            dep.uninstall()

            assert not dep.target_dir.exists()
            assert not dep.version_file.exists()


# ─────────────────────────────────────────────────────────────────────────────
# Tests for PipEngine
# ─────────────────────────────────────────────────────────────────────────────

class TestPipEngine:
    """Tests for the PipEngine class."""

    def test_venv_path_construction(self, tmp_path):
        """PipEngine builds the right venv paths."""
        from app.scripts.installers.base import PipEngine

        with patch("app.scripts.installers.base.resolve_project_root", return_value=tmp_path):
            with patch.object(sys, "platform", "darwin"):
                engine = PipEngine("test_pip", "https://example.com/repo.git", ".venv_test")
                assert engine.venv_dir == tmp_path / ".venv_test"
                assert engine.python_bin == tmp_path / ".venv_test" / "bin" / "python"
                assert engine.bin_path == engine.python_bin

    def test_venv_path_windows(self, tmp_path):
        """PipEngine builds the Windows paths."""
        from app.scripts.installers.base import PipEngine

        with patch("app.scripts.installers.base.resolve_project_root", return_value=tmp_path):
            with patch.object(sys, "platform", "win32"):
                engine = PipEngine("test_pip", "https://example.com/repo.git", ".venv_test")
                assert engine.python_bin == tmp_path / ".venv_test" / "Scripts" / "python.exe"

    def test_is_installed_venv(self, tmp_path):
        """is_installed checks that the venv python is present."""
        from app.scripts.installers.base import PipEngine

        with patch("app.scripts.installers.base.resolve_project_root", return_value=tmp_path):
            engine = PipEngine("test_pip", "https://example.com/repo.git", ".venv_test")
            engine.python_bin.parent.mkdir(parents=True)
            engine.python_bin.write_text("python")
            assert engine.is_installed() is True


class TestFourDGSEngineDep:
    """Tests for FourDGSEngineDep (nerfstudio, isolated in .venv_4dgs)."""

    def test_venv_matches_four_dgs_engine_path(self, tmp_path):
        """The declared venv must match .venv_4dgs, as expected by FourDGSEngine."""
        from app.scripts.installers.four_dgs import FourDGSEngineDep

        with patch("app.scripts.installers.base.resolve_project_root", return_value=tmp_path):
            dep = FourDGSEngineDep()
            assert dep.venv_dir == tmp_path / ".venv_4dgs"

    def test_disabled_by_default(self, tmp_path):
        """No automatic installation while four_dgs_enabled is off."""
        from app.scripts.installers.four_dgs import FourDGSEngineDep

        with patch("app.scripts.installers.base.resolve_project_root", return_value=tmp_path):
            dep = FourDGSEngineDep()
            assert dep.is_enabled_in_config({}) is False
            assert dep.is_enabled_in_config({"four_dgs_enabled": True}) is True
            assert dep.is_enabled_in_config({"four_dgs_params": {"enabled": True}}) is True


# ---------------------------------------------------------------------------
# Third-party repo pinning (audit I16)
# ---------------------------------------------------------------------------

class TestRepoPinning:
    """Every repo we clone, compile and then execute must name a version.

    Unpinned, `update_git()` reset to the default branch, so the code running on
    the user's machine was whatever upstream had pushed that day.
    """

    def test_every_git_backed_dependency_is_pinned(self):
        from app.scripts.installers.extractor_360 import Extractor360EngineDep
        from app.scripts.installers.four_dgs import FourDGSEngineDep
        from app.scripts.installers.sharp import SharpEngineDep

        for cls in (SharpEngineDep, FourDGSEngineDep, Extractor360EngineDep):
            dep = cls()
            assert dep.pinned_ref, f"{cls.__name__} tracks an unpinned branch"

    def test_update_git_checks_out_the_pin(self, tmp_path):
        from app.scripts.installers.base import EngineDependency

        dep = EngineDependency("demo", "https://example.invalid/repo.git", pinned_ref="v1.2.3")
        dep.engines_dir = tmp_path
        dep.target_dir = tmp_path / "demo"
        dep.target_dir.mkdir(parents=True)

        with patch("subprocess.check_call") as mock_call:
            dep.update_git()

        commands = [c.args[0] for c in mock_call.call_args_list]
        assert any("fetch" in cmd for cmd in commands)
        checkout = [cmd for cmd in commands if "checkout" in cmd]
        assert checkout and checkout[0][-1] == "v1.2.3"
        # A pinned dependency must never fall back to pulling the branch tip.
        assert not any("pull" in cmd for cmd in commands)

    def test_unpinned_dependency_still_pulls(self, tmp_path):
        """Backwards compatible: a dependency without a pin keeps the old path."""
        from app.scripts.installers.base import EngineDependency

        dep = EngineDependency("demo", "https://example.invalid/repo.git")
        dep.engines_dir = tmp_path
        dep.target_dir = tmp_path / "demo"
        dep.target_dir.mkdir(parents=True)

        with patch("subprocess.check_call") as mock_call:
            dep.update_git()

        commands = [c.args[0] for c in mock_call.call_args_list]
        assert any("pull" in cmd for cmd in commands)


# ---------------------------------------------------------------------------
# Rosetta 2 reporting (audit I11 remainder)
# ---------------------------------------------------------------------------

class TestRosettaWarning:
    """The warning used to go to stderr, invisible on an icon launch."""

    @patch("app.core.system.is_running_under_rosetta", return_value=False)
    def test_silent_when_native(self, _mock):
        from app.core.system import rosetta_warning
        assert rosetta_warning() is None

    @patch("app.core.system.is_running_under_rosetta", return_value=True)
    def test_message_names_the_cost_and_the_fix(self, _mock):
        from app.core.system import rosetta_warning

        message = rosetta_warning()
        assert message is not None
        assert "Rosetta 2" in message
        assert "ARM64" in message

    @patch("app.core.system.is_running_under_rosetta", return_value=True)
    def test_returned_not_raised(self, _mock):
        """A returned string lets each front end place it where users look."""
        import warnings

        from app.core.system import rosetta_warning

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            rosetta_warning()
        assert caught == []


# ---------------------------------------------------------------------------
# main_install: an engine failing to install must not abort the others (F-012)
# ---------------------------------------------------------------------------

class TestMainInstallFailureIsolation:
    """One engine raising in install() must not stop the following engines.

    Before the fix the two install-mode branches called engine.install()
    without try/except, so a subprocess failure (or the RuntimeError raised
    by the upscayl installer) escaped main_install() and the loop stopped.
    """

    @staticmethod
    def _fake_engine(name, installed=False, install_raises=None, local="", remote=""):
        eng = MagicMock()
        eng.name = name
        eng.is_enabled_in_config.return_value = True
        eng.get_remote_version.return_value = remote
        eng.get_local_version.return_value = local
        state = {"installed": installed}
        eng.is_installed.side_effect = lambda: state["installed"]
        if install_raises is not None:
            def install():
                raise install_raises
        else:
            def install():
                state["installed"] = True
        eng.install.side_effect = install
        return eng

    @staticmethod
    def _manager(tmp_path, engines):
        from app.scripts.installers.base import DependencyManager
        manager = DependencyManager(tmp_path)
        manager.engines = engines
        return manager

    def test_missing_engine_failure_does_not_block_following_engines(self, tmp_path, capsys):
        first = self._fake_engine("alpha", install_raises=RuntimeError("boom"))
        second = self._fake_engine("beta")
        manager = self._manager(tmp_path, {"alpha": first, "beta": second})

        with patch("app.scripts.installers.tools.install_system_dependencies"):
            manager.main_install()

        out = capsys.readouterr().out
        assert "boom" in out
        assert "alpha" in out
        second.install.assert_called_once()

    def test_update_branch_failure_does_not_block_following_engines(self, tmp_path, capsys):
        first = self._fake_engine("gamma", installed=True, local="v1", remote="v2", install_raises=RuntimeError("ups"))
        second = self._fake_engine("delta", installed=True, local="v1", remote="v2")
        manager = self._manager(tmp_path, {"gamma": first, "delta": second})

        with patch("app.scripts.installers.tools.install_system_dependencies"):
            manager.main_install()

        out = capsys.readouterr().out
        assert "ups" in out
        assert "gamma" in out
        second.install.assert_called_once()

    def test_nominal_install_treats_all_engines_without_error(self, tmp_path, capsys):
        first = self._fake_engine("epsilon")
        second = self._fake_engine("zeta")
        manager = self._manager(tmp_path, {"epsilon": first, "zeta": second})

        with patch("app.scripts.installers.tools.install_system_dependencies"):
            manager.main_install()

        first.install.assert_called_once()
        second.install.assert_called_once()
        assert "❌" not in capsys.readouterr().out


class TestGuiStartupReport:
    """Two tiers, plus Rosetta first (launcher._report_missing_dependencies)."""

    def _window(self):
        window = MagicMock()
        window.logged = []
        window.logs_window.append_log = window.logged.append
        return window

    def test_rosetta_is_logged_before_dependencies(self):
        from app.cli import launcher

        window = self._window()
        with patch("app.core.system.rosetta_warning", return_value="⚠️ Rosetta 2"):
            with patch("app.core.system.check_dependencies", return_value=["ffmpeg"]):
                with patch("PySide6.QtWidgets.QMessageBox"):
                    launcher._report_missing_dependencies(window)

        assert window.logged[0] == "⚠️ Rosetta 2"
        assert "ffmpeg" in window.logged[1]

    def test_rosetta_alone_still_reaches_the_log(self):
        from app.cli import launcher

        window = self._window()
        with patch("app.core.system.rosetta_warning", return_value="⚠️ Rosetta 2"):
            with patch("app.core.system.check_dependencies", return_value=[]):
                launcher._report_missing_dependencies(window)

        assert window.logged == ["⚠️ Rosetta 2"]

    def test_feature_binaries_do_not_raise_a_dialog(self):
        """Only core tools interrupt; per-feature ones stay in the log."""
        from app.cli import launcher

        window = self._window()
        with patch("app.core.system.rosetta_warning", return_value=None):
            with patch("app.core.system.check_dependencies",
                       return_value=["glomap (mapper Glomap)"]):
                with patch("PySide6.QtWidgets.QMessageBox") as box:
                    launcher._report_missing_dependencies(window)

        assert box.called is False
        assert len(window.logged) == 1
