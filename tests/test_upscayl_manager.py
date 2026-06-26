"""Tests pour upscayl_manager.py."""
import os
import sys
import zipfile
import tarfile
import io
import hashlib
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, ANY

import pytest

# Patch send2trash at module level if missing (used by engine.py via upscayl_manager imports)
for _mod_name in ["send2trash", "cv2"]:
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = MagicMock()

from app.scripts.checksum_verifier import verify_download, verify_download_strict, compute_file_sha256


# ─────────────────────────────────────────────────────────────────────────────
# Tests for checksum_verifier (used by upscayl_manager)
# ─────────────────────────────────────────────────────────────────────────────

class TestVerifyDownload:
    """Tests pour verify_download() et verify_download_strict()."""

    def test_valid_checksum(self, tmp_path):
        """SHA256 valide → True."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"hello world")
        expected = hashlib.sha256(b"hello world").hexdigest()
        assert verify_download(f, expected) is True

    def test_invalid_checksum(self, tmp_path):
        """SHA256 invalide → False."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"hello world")
        assert verify_download(f, "0000000000000000000000000000000000000000000000000000000000000000") is False

    def test_empty_hash_returns_true(self, tmp_path):
        """Empreinte vide → True (non-strict mode, compatibilité descendante)."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"some data")
        assert verify_download(f, "") is True

    def test_nonexistent_file(self, tmp_path):
        """Fichier inexistant → False."""
        f = tmp_path / "nonexistent.bin"
        assert verify_download(f, "aa" * 32) is False

    def test_empty_hash_nonexistent_file(self, tmp_path):
        """Hash vide + fichier inexistant → True (le hash vide court-circuite)."""
        f = tmp_path / "nonexistent.bin"
        assert verify_download(f, "") is True

    def test_strict_empty_hash_returns_false(self, tmp_path):
        """verify_download_strict avec hash vide → False."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"data")
        assert verify_download_strict(f, "") is False

    def test_compute_file_sha256(self, tmp_path):
        """compute_file_sha256 retourne le bon hash."""
        f = tmp_path / "data.bin"
        f.write_bytes(b"test data" * 1000)
        expected = hashlib.sha256(b"test data" * 1000).hexdigest()
        assert compute_file_sha256(f) == expected


# ─────────────────────────────────────────────────────────────────────────────
# Tests for upscayl_manager functions
# ─────────────────────────────────────────────────────────────────────────────

class TestDownloadModelFiles:
    """Tests pour download_model_files()."""

    @patch("app.upscayl_manager.get_models_dir")
    @patch("app.upscayl_manager.urllib.request.urlopen")
    def test_download_success(self, mock_urlopen, mock_get_models_dir, tmp_path):
        """Téléchargement réussi des fichiers .bin et .param."""
        models_dir = tmp_path / "models" / "upscayl"
        models_dir.mkdir(parents=True)
        # We need the models_dir to exist (get_models_dir creates it internally)
        # Since we mock get_models_dir, we need to create it manually
        mock_get_models_dir.return_value = models_dir

        # Mock HTTP responses with proper context manager support
        mock_resp_bin = MagicMock()
        mock_resp_bin.read.return_value = b"x" * 1024  # > 512 bytes
        mock_resp_bin.__enter__.return_value = mock_resp_bin
        mock_resp_param = MagicMock()
        mock_resp_param.read.return_value = b"y" * 1024
        mock_resp_param.__enter__.return_value = mock_resp_param

        # Return different responses for each URL
        mock_urlopen.side_effect = [mock_resp_bin, mock_resp_param]

        from app.upscayl_manager import download_model_files

        result = download_model_files(
            "https://example.com/model.bin",
            "https://example.com/model.param",
            "test-model",
        )
        assert result is True
        assert (models_dir / "test-model.bin").exists()
        assert (models_dir / "test-model.param").exists()
        assert (models_dir / "test-model.bin").read_bytes() == b"x" * 1024
        assert (models_dir / "test-model.param").read_bytes() == b"y" * 1024

    @patch("app.upscayl_manager.get_models_dir")
    @patch("app.upscayl_manager.urllib.request.urlopen")
    def test_download_too_small(self, mock_urlopen, mock_get_models_dir, tmp_path):
        """Fichier trop petit (moins de 512 octets) → False."""
        models_dir = tmp_path / "models" / "upscayl"
        models_dir.mkdir(parents=True)
        mock_get_models_dir.return_value = models_dir

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"small"  # < 512 bytes

        mock_urlopen.return_value = mock_resp

        from app.upscayl_manager import download_model_files

        result = download_model_files(
            "https://example.com/model.bin",
            "https://example.com/model.param",
            "test-model",
        )
        assert result is False
        # The small file should have been deleted
        assert not (models_dir / "test-model.bin").exists()

    @patch("app.upscayl_manager.get_models_dir")
    @patch("app.upscayl_manager.urllib.request.urlopen")
    def test_download_http_error(self, mock_urlopen, mock_get_models_dir, tmp_path):
        """Erreur HTTP → False."""
        models_dir = tmp_path / "models" / "upscayl"
        models_dir.mkdir(parents=True)
        mock_get_models_dir.return_value = models_dir

        mock_urlopen.side_effect = Exception("Connection error")

        from app.upscayl_manager import download_model_files

        result = download_model_files(
            "https://example.com/model.bin",
            "https://example.com/model.param",
            "test-model",
        )
        assert result is False

    @patch("app.upscayl_manager.get_models_dir")
    def test_already_downloaded(self, mock_get_models_dir, tmp_path):
        """Fichier déjà présent avec taille > 1024 → skip download."""
        models_dir = tmp_path / "models" / "upscayl"
        models_dir.mkdir(parents=True)
        (models_dir / "test-model.bin").write_bytes(b"x" * 2048)
        (models_dir / "test-model.param").write_bytes(b"y" * 2048)
        mock_get_models_dir.return_value = models_dir

        from app.upscayl_manager import download_model_files

        result = download_model_files(
            "https://example.com/model.bin",
            "https://example.com/model.param",
            "test-model",
        )
        assert result is True


class TestExtractArchive:
    """Tests pour _extract_archive() — protection Zip Slip."""

    @patch("app.upscayl_manager.get_bin_dir")
    @patch("app.upscayl_manager.get_models_dir")
    def test_zip_zip_slip_blocked(self, mock_get_models_dir, mock_get_bin_dir, tmp_path):
        """Zip contenant un chemin avec ../ — seuls les fichiers autorisés sont extraits par basename."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(parents=True)
        models_dir = tmp_path / "models" / "upscayl"
        models_dir.mkdir(parents=True)
        mock_get_bin_dir.return_value = bin_dir
        mock_get_models_dir.return_value = models_dir

        # Create a malicious zip in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("../../etc/passwd", "evil")
            # Also a valid file to ensure extraction works for safe files
            zf.writestr("upscayl-bin", b"binary_content")
        zip_buffer.seek(0)

        archive_path = tmp_path / "archive.zip"
        archive_path.write_bytes(zip_buffer.read())

        from app.upscayl_manager import _extract_archive

        log_messages = []
        _extract_archive(archive_path, bin_dir, models_dir, log_messages.append)

        # The malicious file should not have been extracted outside
        assert not (tmp_path / "etc" / "passwd").exists()
        # But upscayl-bin should have been extracted (basename check passes)
        assert (bin_dir / "upscayl-bin").exists()
        assert (bin_dir / "upscayl-bin").read_bytes() == b"binary_content"

    @patch("app.upscayl_manager.get_bin_dir")
    @patch("app.upscayl_manager.get_models_dir")
    def test_tar_zip_slip_blocked(self, mock_get_models_dir, mock_get_bin_dir, tmp_path):
        """Archive tar.gz contenant un chemin avec ../ — extrait par basename."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(parents=True)
        models_dir = tmp_path / "models" / "upscayl"
        models_dir.mkdir(parents=True)
        mock_get_bin_dir.return_value = bin_dir
        mock_get_models_dir.return_value = models_dir

        # Create a malicious tar
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tf:
            # Adding a file with ../
            info = tarfile.TarInfo(name="../../evil.sh")
            info.size = 4
            tf.addfile(info, io.BytesIO(b"evil"))
            # Add a valid model file
            info2 = tarfile.TarInfo(name="realesrgan-x4plus.bin")
            info2.size = 5
            tf.addfile(info2, io.BytesIO(b"model"))
        tar_buffer.seek(0)

        archive_path = tmp_path / "archive.tar.gz"
        archive_path.write_bytes(tar_buffer.read())

        from app.upscayl_manager import _extract_archive

        log_messages = []
        _extract_archive(archive_path, bin_dir, models_dir, log_messages.append)

        # The malicious file should not have been extracted outside
        assert not (tmp_path / "evil.sh").exists()
        # But model file should be extracted (basename check passes)
        assert (models_dir / "realesrgan-x4plus.bin").exists()

    @patch("app.upscayl_manager.get_bin_dir")
    @patch("app.upscayl_manager.get_models_dir")
    def test_unknown_format(self, mock_get_models_dir, mock_get_bin_dir, tmp_path):
        """Format d'archive inconnu → log et pas d'erreur."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(parents=True)
        models_dir = tmp_path / "models" / "upscayl"
        models_dir.mkdir(parents=True)
        mock_get_bin_dir.return_value = bin_dir
        mock_get_models_dir.return_value = models_dir

        archive_path = tmp_path / "archive.rar"
        archive_path.write_bytes(b"not a real archive")

        from app.upscayl_manager import _extract_archive

        log_messages = []
        _extract_archive(archive_path, bin_dir, models_dir, log_messages.append)

        assert any("Unknown archive" in m for m in log_messages)
        assert not (bin_dir / "upscayl-bin").exists()


class TestDownloadBinary:
    """Tests pour download_binary()."""

    @patch("app.upscayl_manager._fetch_release")
    @patch("app.upscayl_manager.get_bin_dir")
    @patch("app.upscayl_manager.urllib.request.urlopen")
    @patch("app.upscayl_manager.load_expected_checksums")
    @patch("app.upscayl_manager.verify_download")
    @patch("app.upscayl_manager.get_models_dir")
    @patch("app.upscayl_manager._extract_archive")
    @patch("app.upscayl_manager.os.chmod")
    def test_download_binary_success(
        self,
        mock_chmod,
        mock_extract,
        mock_get_models_dir,
        mock_verify,
        mock_load_checksums,
        mock_urlopen,
        mock_get_bin_dir,
        mock_fetch_release,
        tmp_path,
    ):
        """Téléchargement réussi du binaire upscayl."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(parents=True)
        mock_get_bin_dir.return_value = bin_dir
        mock_get_models_dir.return_value = tmp_path / "models" / "upscayl"
        mock_fetch_release.return_value = {
            "assets": [
                {
                    "name": "upscayl-windows-x86_64.zip",
                    "size": 5 * 1024 * 1024,
                    "browser_download_url": "https://example.com/upscayl.zip",
                }
            ]
        }
        mock_verify.return_value = True
        mock_load_checksums.return_value = {"windows_upscayl": "aa" * 32}

        # Mock HTTP download with context manager
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"archive_content"
        # Ensure __enter__ returns the mock for with-statement
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        from app.upscayl_manager import download_binary

        # Since _extract_archive is mocked, create the expected binary manually
        (bin_dir / "upscayl-bin").write_text("binary")

        result = download_binary(log_callback=print)

        assert result == bin_dir / "upscayl-bin"
        mock_chmod.assert_called_once_with(bin_dir / "upscayl-bin", 0o755)
        assert mock_urlopen.call_count >= 1

    @patch("app.upscayl_manager._fetch_release")
    def test_no_windows_asset(self, mock_fetch_release):
        """Aucun asset Windows → RuntimeError."""
        mock_fetch_release.return_value = {
            "assets": [{"name": "upscayl-linux-x86_64.tar.gz"}]
        }

        from app.upscayl_manager import download_binary

        with pytest.raises(RuntimeError, match="No Windows release asset"):
            download_binary()

    @patch("app.upscayl_manager._fetch_release")
    @patch("app.upscayl_manager.get_bin_dir")
    @patch("app.upscayl_manager.urllib.request.urlopen")
    def test_download_http_error(
        self, mock_urlopen, mock_get_bin_dir, mock_fetch_release, tmp_path
    ):
        """Erreur HTTP → RuntimeError."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(parents=True)
        mock_get_bin_dir.return_value = bin_dir
        mock_fetch_release.return_value = {
            "assets": [
                {
                    "name": "upscayl-windows-x86_64.zip",
                    "size": 5 * 1024 * 1024,
                    "browser_download_url": "https://example.com/upscayl.zip",
                }
            ]
        }
        mock_urlopen.side_effect = Exception("Download failed")

        from app.upscayl_manager import download_binary

        with pytest.raises(Exception, match="Download failed"):
            download_binary()


class TestUpscaylRun:
    """Tests pour run_upscayl()."""

    @patch("app.upscayl_manager.find_binary")
    @patch("app.upscayl_manager.subprocess.Popen")
    @patch("app.upscayl_manager.os.access")
    def test_run_basic(self, mock_access, mock_popen, mock_find_binary, tmp_path):
        """Exécution de base de upscayl-bin."""
        mock_find_binary.return_value = Path("/usr/local/bin/upscayl-bin")
        mock_access.return_value = True  # binary appears executable

        # Create a mock process that can iterate over stdout
        mock_proc = MagicMock()
        mock_proc.stdout = iter(["Processing...\n", "Done!\n"])
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        from app.upscayl_manager import run_upscayl

        log_msgs = []
        done_results = []

        run_upscayl(
            str(tmp_path / "input"),
            str(tmp_path / "output"),
            {"model_id": "realesrgan-x4plus", "scale": 4},
            log_callback=log_msgs.append,
            done_callback=done_results.append,
        )

        assert len(done_results) == 1
        assert done_results[0] is True

    @patch("app.upscayl_manager.find_binary")
    def test_no_binary(self, mock_find_binary):
        """Aucun binaire trouvé → done_callback(False)."""
        mock_find_binary.return_value = None

        from app.upscayl_manager import run_upscayl

        done_results = []
        run_upscayl("/in", "/out", {}, done_callback=done_results.append)

        assert len(done_results) == 1
        assert done_results[0] is False

    @patch("app.upscayl_manager.find_binary")
    def test_no_model(self, mock_find_binary):
        """Aucun model_id → done_callback(False)."""
        mock_find_binary.return_value = Path("/usr/local/bin/upscayl-bin")

        from app.upscayl_manager import run_upscayl

        done_results = []
        run_upscayl("/in", "/out", {}, done_callback=done_results.append)

        assert len(done_results) == 1
        assert done_results[0] is False


class TestUpscaylHelpers:
    """Tests pour les fonctions helper du module upscayl_manager."""

    def test_find_windows_asset(self):
        """_find_windows_asset trouve le bon asset."""
        from app.upscayl_manager import _find_windows_asset

        assets = [
            {"name": "upscayl-linux-x86_64.tar.gz"},
            {"name": "upscayl-macos-arm64.tar.gz"},
            {"name": "upscayl-windows-x86_64.zip"},
        ]
        result = _find_windows_asset(assets)
        assert result is not None
        assert "windows" in result["name"]

    def test_find_windows_asset_fallback(self):
        """_find_windows_asset utilise le fallback 'win' si nécessaire."""
        from app.upscayl_manager import _find_windows_asset

        assets = [
            {"name": "upscayl-win64.zip"},
        ]
        result = _find_windows_asset(assets)
        assert result is not None

    def test_find_windows_asset_none(self):
        """_find_windows_asset retourne None si aucun asset Windows."""
        from app.upscayl_manager import _find_windows_asset

        assets = [
            {"name": "upscayl-linux-x86_64.tar.gz"},
            {"name": "upscayl-macos-arm64.tar.gz"},
        ]
        result = _find_windows_asset(assets)
        assert result is None

    def test_get_bin_dir(self, tmp_path):
        """get_bin_dir retourne le chemin attendu."""
        with patch("app.upscayl_manager.resolve_project_root", return_value=tmp_path):
            from app.upscayl_manager import get_bin_dir
            assert get_bin_dir() == tmp_path / "bin"

    def test_get_models_dir(self, tmp_path):
        """get_models_dir crée le dossier et retourne le chemin."""
        with patch("app.upscayl_manager.resolve_project_root", return_value=tmp_path):
            from app.upscayl_manager import get_models_dir
            result = get_models_dir()
            assert result == tmp_path / "models" / "upscayl"
            assert result.exists()

    def test_is_using_local_binary(self, tmp_path):
        """is_using_local_binary détecte le binaire local."""
        with patch("app.upscayl_manager.resolve_project_root", return_value=tmp_path):
            from app.upscayl_manager import is_using_local_binary
            bin_dir = tmp_path / "bin"
            bin_dir.mkdir(parents=True)
            binary = bin_dir / "upscayl-bin"
            binary.write_text("binary")
            os.chmod(binary, 0o755)
            assert is_using_local_binary() is True

    def test_is_using_local_binary_not_found(self, tmp_path):
        """is_using_local_binary retourne False si absent."""
        with patch("app.upscayl_manager.resolve_project_root", return_value=tmp_path):
            from app.upscayl_manager import is_using_local_binary
            assert is_using_local_binary() is False
