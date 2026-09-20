"""Tests for app.scripts.setup_dependencies.py and app/core/system.py.
The patches now target app.scripts.installers.* where the functions are defined,
while the imports stay from app.scripts.setup_dependencies (re-exports).
"""
import json
import subprocess
import sys
from unittest.mock import patch

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

    @patch("app.core.system.resolve_project_root")
    def test_no_version_file(self, mock_root, tmp_path):
        """No version file → returns 'release' (default)."""
        mock_root.return_value = tmp_path

        from app.core.system import get_brush_build_mode
        assert get_brush_build_mode() == "release"

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
