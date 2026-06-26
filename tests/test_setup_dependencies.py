"""Tests pour app.scripts.setup_dependencies.py et app/core/system.py.
Les patches ciblent maintenant app.scripts.installers.* où les fonctions sont définies,
tandis que les imports restent depuis app.scripts.setup_dependencies (réexportations)."""
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, ANY
import tempfile
import json

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Tests for checksum_verifier (used by setup_dependencies)
# ─────────────────────────────────────────────────────────────────────────────

class TestChecksumVerifier:
    """Tests pour les fonctions de vérification de checksum."""

    def test_load_expected_checksums_success(self, tmp_path):
        """load_expected_checksums retourne le dict JSON."""
        # Patch the CHECKSUMS_PATH to point to a temp file
        checksums_file = tmp_path / "checksums.json"
        checksums_file.write_text(json.dumps({"darwin_brush": "abc123"}))

        with patch("app.scripts.checksum_verifier.CHECKSUMS_PATH", checksums_file):
            from app.scripts.checksum_verifier import load_expected_checksums
            result = load_expected_checksums()
            assert result == {"darwin_brush": "abc123"}

    @patch("app.scripts.checksum_verifier.CHECKSUMS_PATH")
    def test_load_expected_checksums_not_found(self, mock_path):
        """load_expected_checksums sans fichier → dict vide."""
        mock_path.exists.return_value = False

        from app.scripts.checksum_verifier import load_expected_checksums
        result = load_expected_checksums()
        assert result == {}

    def test_load_expected_checksums_invalid_json(self, tmp_path):
        """load_expected_checksums avec JSON invalide → dict vide."""
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
    """Tests pour system.get_brush_build_mode()."""

    @patch("app.core.system.resolve_project_root")
    def test_source_mode_detected(self, mock_root, tmp_path):
        """Version file avec 'source' → retourne 'source'."""
        engines_dir = tmp_path / "engines"
        engines_dir.mkdir(parents=True)
        version_file = engines_dir / "brush.version"
        version_file.write_text("abc12345-source")
        mock_root.return_value = tmp_path

        from app.core.system import get_brush_build_mode
        assert get_brush_build_mode() == "source"

    @patch("app.core.system.resolve_project_root")
    def test_release_mode_detected(self, mock_root, tmp_path):
        """Version file sans 'source' → retourne 'release'."""
        engines_dir = tmp_path / "engines"
        engines_dir.mkdir(parents=True)
        version_file = engines_dir / "brush.version"
        version_file.write_text("v0.3.0")
        mock_root.return_value = tmp_path

        from app.core.system import get_brush_build_mode
        assert get_brush_build_mode() == "release"

    @patch("app.core.system.resolve_project_root")
    def test_no_version_file(self, mock_root, tmp_path):
        """Pas de version file → retourne 'release' (défaut)."""
        mock_root.return_value = tmp_path

        from app.core.system import get_brush_build_mode
        assert get_brush_build_mode() == "release"

    @patch("app.core.system.resolve_project_root")
    def test_empty_version_file(self, mock_root, tmp_path):
        """Version file vide → retourne 'release'."""
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
    """Tests pour system.check_dependencies()."""

    @patch("app.core.system.resolve_binary")
    def test_all_dependencies_present(self, mock_resolve_binary):
        """Toutes les dépendances présentes → liste vide."""
        mock_resolve_binary.side_effect = lambda x: x  # found
        # send2trash is already in sys.modules (possibly mocked), patch find_spec
        import importlib.util
        with patch.object(importlib.util, 'find_spec', return_value=True):
            from app.core.system import check_dependencies
            missing = check_dependencies()
            assert missing == []

    @patch("app.core.system.resolve_binary")
    def test_some_missing(self, mock_resolve_binary):
        """Dépendances manquantes → liste non vide."""
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
        """Certaines dépendances manquantes."""
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
    """Tests pour les fonctions utilitaires de setup_dependencies.py."""

    def test_relax_requirements(self, tmp_path):
        """relax_requirements change torch== en torch>=."""
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
        """check_cargo vérifie la présence de cargo."""
        with patch("app.scripts.installers.tools.shutil.which") as mock_which:
            mock_which.return_value = "/usr/local/bin/cargo"
            from app.scripts.installers.tools import check_cargo
            assert check_cargo() is True

    def test_check_cargo_not_found(self):
        """check_cargo retourne False si cargo absent."""
        with patch("app.scripts.installers.tools.shutil.which") as mock_which:
            mock_which.return_value = None
            from app.scripts.installers.tools import check_cargo
            assert check_cargo() is False

    def test_check_winget(self):
        """check_winget vérifie la présence de winget."""
        with patch("app.scripts.installers.tools.shutil.which") as mock_which:
            mock_which.return_value = r"C:\\Windows\\winget.exe"
            from app.scripts.installers.tools import check_winget
            assert check_winget() is True

    def test_check_node(self):
        """check_node vérifie node et npm."""
        with patch("app.scripts.installers.tools.shutil.which") as mock_which:
            mock_which.side_effect = lambda x: f"/usr/local/bin/{x}" if x in ("node", "npm") else None
            from app.scripts.installers.tools import check_node
            assert check_node() is True

    def test_check_node_missing_npm(self):
        """check_node retourne False si npm absent."""
        with patch("app.scripts.installers.tools.shutil.which") as mock_which:
            def which_side_effect(name):
                if name == "node":
                    return "/usr/local/bin/node"
                return None
            mock_which.side_effect = which_side_effect
            from app.scripts.installers.tools import check_node
            assert check_node() is False

    def test_check_cmake_ninja(self):
        """check_cmake_ninja vérifie cmake et ninja."""
        with patch("app.scripts.installers.tools.shutil.which") as mock_which:
            mock_which.side_effect = lambda x: f"/usr/local/bin/{x}"
            from app.scripts.installers.tools import check_cmake_ninja
            assert check_cmake_ninja() is True

    def test_get_remote_version(self):
        """get_remote_version utilise git ls-remote."""
        with patch("app.scripts.installers.tools.subprocess.check_output") as mock_check:
            mock_check.return_value = "abc123def\tHEAD\n"
            from app.scripts.installers.tools import get_remote_version
            result = get_remote_version("https://github.com/test/repo.git")
            assert result == "abc123def"

    def test_get_remote_version_failure(self):
        """get_remote_version retourne None en cas d'erreur."""
        with patch("app.scripts.installers.tools.subprocess.check_output") as mock_check:
            mock_check.side_effect = Exception("git error")
            from app.scripts.installers.tools import get_remote_version
            result = get_remote_version("https://github.com/test/repo.git")
            assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests for EngineDependency
# ─────────────────────────────────────────────────────────────────────────────

class TestEngineDependency:
    """Tests pour la classe EngineDependency."""

    def test_is_installed(self, tmp_path):
        """is_installed vérifie l'existence du binaire."""
        from app.scripts.installers.base import EngineDependency

        with patch("app.scripts.installers.base.resolve_project_root", return_value=tmp_path):
            dep = EngineDependency("test_engine", bin_name="test_bin")
            # Create the binary
            dep.bin_path.parent.mkdir(parents=True, exist_ok=True)
            dep.bin_path.write_text("binary")
            assert dep.is_installed() is True

    def test_is_not_installed(self, tmp_path):
        """is_installed retourne False si binaire absent."""
        from app.scripts.installers.base import EngineDependency

        with patch("app.scripts.installers.base.resolve_project_root", return_value=tmp_path):
            dep = EngineDependency("test_engine", bin_name="test_bin")
            assert dep.is_installed() is False

    def test_save_and_get_local_version(self, tmp_path):
        """save_local_version puis get_local_version."""
        from app.scripts.installers.base import EngineDependency

        with patch("app.scripts.installers.base.resolve_project_root", return_value=tmp_path):
            dep = EngineDependency("test_engine", bin_name="test_bin")
            dep.save_local_version("v1.0.0")
            assert dep.get_local_version() == "v1.0.0"

    def test_get_local_version_missing(self, tmp_path):
        """get_local_version sans fichier → chaîne vide."""
        from app.scripts.installers.base import EngineDependency

        with patch("app.scripts.installers.base.resolve_project_root", return_value=tmp_path):
            dep = EngineDependency("test_engine", bin_name="test_bin")
            assert dep.get_local_version() == ""

    def test_is_enabled_in_config(self, tmp_path):
        """is_enabled_in_config utilise la config."""
        from app.scripts.installers.base import EngineDependency

        dep = EngineDependency("test_engine", bin_name="test_bin")
        config = {"test_engine_enabled": True}
        assert dep.is_enabled_in_config(config) is True

    def test_is_enabled_in_config_default(self, tmp_path):
        """is_enabled_in_config retourne True par défaut."""
        from app.scripts.installers.base import EngineDependency

        dep = EngineDependency("test_engine", bin_name="test_bin")
        config = {}
        assert dep.is_enabled_in_config(config) is True

    def test_uninstall(self, tmp_path):
        """uninstall supprime target_dir et version_file."""
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
    """Tests pour la classe PipEngine."""

    def test_venv_path_construction(self, tmp_path):
        """PipEngine construit les bons chemins de venv."""
        from app.scripts.installers.base import PipEngine

        with patch("app.scripts.installers.base.resolve_project_root", return_value=tmp_path):
            with patch.object(sys, "platform", "darwin"):
                engine = PipEngine("test_pip", "https://example.com/repo.git", ".venv_test")
                assert engine.venv_dir == tmp_path / ".venv_test"
                assert engine.python_bin == tmp_path / ".venv_test" / "bin" / "python"
                assert engine.bin_path == engine.python_bin

    def test_venv_path_windows(self, tmp_path):
        """PipEngine construit les chemins Windows."""
        from app.scripts.installers.base import PipEngine

        with patch("app.scripts.installers.base.resolve_project_root", return_value=tmp_path):
            with patch.object(sys, "platform", "win32"):
                engine = PipEngine("test_pip", "https://example.com/repo.git", ".venv_test")
                assert engine.python_bin == tmp_path / ".venv_test" / "Scripts" / "python.exe"

    def test_is_installed_venv(self, tmp_path):
        """is_installed vérifie la présence du python du venv."""
        from app.scripts.installers.base import PipEngine

        with patch("app.scripts.installers.base.resolve_project_root", return_value=tmp_path):
            engine = PipEngine("test_pip", "https://example.com/repo.git", ".venv_test")
            engine.python_bin.parent.mkdir(parents=True)
            engine.python_bin.write_text("python")
            assert engine.is_installed() is True


class TestColmapAssetSelection:
    """Tests pour mapping.find_colmap_windows_asset()."""

    def test_prefers_cuda_build(self):
        from app.scripts.installers.mapping import find_colmap_windows_asset
        assets = [
            {"name": "colmap-x64-windows-nocuda.zip"},
            {"name": "colmap-x64-windows-cuda.zip"},
            {"name": "colmap-x64-linux.zip"},
        ]
        result = find_colmap_windows_asset(assets, prefer_cuda=True)
        assert result is not None
        assert result["name"] == "colmap-x64-windows-cuda.zip"

    def test_never_picks_nocuda_as_cuda(self):
        """nocuda must not be mistaken for a CUDA build."""
        from app.scripts.installers.mapping import find_colmap_windows_asset
        assets = [{"name": "colmap-x64-windows-nocuda.zip"}]
        # prefer_cuda=True finds no cuda build, falls back to any windows zip
        result = find_colmap_windows_asset(assets, prefer_cuda=True)
        assert result["name"] == "colmap-x64-windows-nocuda.zip"  # fallback, not CUDA match

    def test_fallback_any_windows_zip(self):
        from app.scripts.installers.mapping import find_colmap_windows_asset
        assets = [{"name": "colmap-x64-windows-nocuda.zip"}, {"name": "src.tar.gz"}]
        result = find_colmap_windows_asset(assets, prefer_cuda=False)
        assert result["name"] == "colmap-x64-windows-nocuda.zip"

    def test_no_windows_asset(self):
        from app.scripts.installers.mapping import find_colmap_windows_asset
        assets = [{"name": "colmap-x64-linux.zip"}, {"name": "src.tar.gz"}]
        assert find_colmap_windows_asset(assets) is None


# Import subprocess for legacy tests
import subprocess
