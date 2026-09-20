"""Tests for upscayl_manager.py.
"""
import hashlib
import io
import sys
import tarfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Patch send2trash at module level if missing (used by engine.py via upscayl_manager imports)
for _mod_name in ["send2trash", "cv2"]:
    if _mod_name not in sys.modules:
        try:
            __import__(_mod_name)  # keep real module if installed — avoids clobbering cv2/numpy session-wide
        except ImportError:
            sys.modules[_mod_name] = MagicMock()

from app.scripts.checksum_verifier import compute_file_sha256, verify_download, verify_download_strict  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Tests for checksum_verifier (used by upscayl_manager)
# ─────────────────────────────────────────────────────────────────────────────

class TestVerifyDownload:
    """Tests for verify_download() and verify_download_strict()."""

    def test_valid_checksum(self, tmp_path):
        """Valid SHA256 → True."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"hello world")
        expected = hashlib.sha256(b"hello world").hexdigest()
        assert verify_download(f, expected) is True

    def test_invalid_checksum(self, tmp_path):
        """Invalid SHA256 → False."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"hello world")
        assert verify_download(f, "0000000000000000000000000000000000000000000000000000000000000000") is False

    def test_empty_hash_returns_true(self, tmp_path):
        """Empty fingerprint → True (non-strict mode, backward compatibility)."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"some data")
        assert verify_download(f, "") is True

    def test_nonexistent_file(self, tmp_path):
        """Non-existent file → False."""
        f = tmp_path / "nonexistent.bin"
        assert verify_download(f, "aa" * 32) is False

    def test_empty_hash_nonexistent_file(self, tmp_path):
        """Empty hash + non-existent file → True (the empty hash short-circuits)."""
        f = tmp_path / "nonexistent.bin"
        assert verify_download(f, "") is True

    def test_strict_empty_hash_returns_false(self, tmp_path):
        """verify_download_strict with an empty hash → False."""
        f = tmp_path / "test.bin"
        f.write_bytes(b"data")
        assert verify_download_strict(f, "") is False

    def test_compute_file_sha256(self, tmp_path):
        """compute_file_sha256 returns the right hash."""
        f = tmp_path / "data.bin"
        f.write_bytes(b"test data" * 1000)
        expected = hashlib.sha256(b"test data" * 1000).hexdigest()
        assert compute_file_sha256(f) == expected


# ─────────────────────────────────────────────────────────────────────────────
# Tests for upscayl_manager functions
# ─────────────────────────────────────────────────────────────────────────────

class TestDownloadModelFiles:
    """Tests for download_model_files()."""

    @patch("app.upscayl_manager.get_models_dir")
    @patch("app.upscayl_manager.urllib.request.urlopen")
    def test_download_success(self, mock_urlopen, mock_get_models_dir, tmp_path):
        """Successful download of the .bin and .param files."""
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
        """File too small (under 512 bytes) → False."""
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
        """HTTP error → False."""
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
        """File already present with size > 1024 → download skipped."""
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
    """Tests for _extract_archive() — Zip Slip protection."""

    @patch("app.upscayl_manager.get_bin_dir")
    @patch("app.upscayl_manager.get_models_dir")
    def test_zip_zip_slip_blocked(self, mock_get_models_dir, mock_get_bin_dir, tmp_path):
        """Zip holding a path with ../ — only the allowed files are extracted by basename."""
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
        """tar.gz archive holding a path with ../ — extracted by basename."""
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
        """Unknown archive format → logged, no error."""
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
    """Tests for download_binary()."""

    @patch("app.upscayl_manager._fetch_release")
    @patch("app.upscayl_manager.get_bin_dir")
    @patch("app.upscayl_manager.urllib.request.urlopen")
    @patch("app.upscayl_manager.load_expected_checksums")
    @patch("app.upscayl_manager.verify_download_strict")
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
        """Successful download of the upscayl binary."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(parents=True)
        mock_get_bin_dir.return_value = bin_dir
        mock_get_models_dir.return_value = tmp_path / "models" / "upscayl"
        mock_fetch_release.return_value = {
            "assets": [
                {
                    "name": "upscayl-macos-arm64.tar.gz",
                    "size": 5 * 1024 * 1024,
                    "browser_download_url": "https://example.com/upscayl.tar.gz",
                }
            ]
        }
        mock_verify.return_value = True
        mock_load_checksums.return_value = {"darwin_upscayl": "aa" * 32}

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
    def test_no_macos_asset(self, mock_fetch_release):
        """No macOS asset → RuntimeError."""
        mock_fetch_release.return_value = {
            "assets": [{"name": "upscayl-linux-x86_64.tar.gz"}]
        }

        from app.upscayl_manager import download_binary

        with pytest.raises(RuntimeError, match="No macOS release asset"):
            download_binary()

    @patch("app.upscayl_manager._fetch_release")
    @patch("app.upscayl_manager.get_bin_dir")
    @patch("app.upscayl_manager.urllib.request.urlopen")
    def test_download_http_error(
        self, mock_urlopen, mock_get_bin_dir, mock_fetch_release, tmp_path
    ):
        """HTTP error → RuntimeError."""
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(parents=True)
        mock_get_bin_dir.return_value = bin_dir
        mock_fetch_release.return_value = {
            "assets": [
                {
                    "name": "upscayl-macos-arm64.tar.gz",
                    "size": 5 * 1024 * 1024,
                    "browser_download_url": "https://example.com/upscayl.tar.gz",
                }
            ]
        }
        mock_urlopen.side_effect = Exception("Download failed")

        from app.upscayl_manager import download_binary

        with pytest.raises(Exception, match="Download failed"):
            download_binary()


class TestUpscaylRun:
    """Tests for run_upscayl()."""

    @patch("app.upscayl_manager.find_binary")
    @patch("app.upscayl_manager.subprocess.Popen")
    @patch("app.upscayl_manager.os.access")
    def test_run_basic(self, mock_access, mock_popen, mock_find_binary, tmp_path):
        """Basic run of upscayl-bin."""
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
        """No binary found → done_callback(False)."""
        mock_find_binary.return_value = None

        from app.upscayl_manager import run_upscayl

        done_results = []
        run_upscayl("/in", "/out", {}, done_callback=done_results.append)

        assert len(done_results) == 1
        assert done_results[0] is False

    @patch("app.upscayl_manager.find_binary")
    def test_no_model(self, mock_find_binary):
        """No model_id → done_callback(False)."""
        mock_find_binary.return_value = Path("/usr/local/bin/upscayl-bin")

        from app.upscayl_manager import run_upscayl

        done_results = []
        run_upscayl("/in", "/out", {}, done_callback=done_results.append)

        assert len(done_results) == 1
        assert done_results[0] is False


class TestUpscaylHelpers:
    """Tests for the helper functions of the upscayl_manager module."""

    def test_find_macos_asset(self):
        """_find_macos_asset finds the right asset."""
        from app.upscayl_manager import _find_macos_asset

        assets = [
            {"name": "upscayl-linux-x86_64.tar.gz"},
            {"name": "upscayl-macos-arm64.tar.gz"},
            {"name": "upscayl-windows-x86_64.zip"},
        ]
        result = _find_macos_asset(assets)
        assert result is not None
        assert "macos" in result["name"]

    def test_find_macos_asset_fallback(self):
        """_find_macos_asset falls back on 'mac' when arm64 is missing."""
        from app.upscayl_manager import _find_macos_asset

        assets = [
            {"name": "upscayl-macos-universal.tar.gz"},
        ]
        result = _find_macos_asset(assets)
        assert result is not None

    def test_find_macos_asset_none(self):
        """_find_macos_asset returns None when there is no macOS asset."""
        from app.upscayl_manager import _find_macos_asset

        assets = [
            {"name": "upscayl-linux-x86_64.tar.gz"},
            {"name": "upscayl-windows-x86_64.zip"},
        ]
        result = _find_macos_asset(assets)
        assert result is None

    def test_get_bin_dir(self, tmp_path):
        """get_bin_dir returns the expected path."""
        with patch("app.upscayl_manager.resolve_project_root", return_value=tmp_path):
            from app.upscayl_manager import get_bin_dir
            assert get_bin_dir() == tmp_path / "bin"

    def test_get_models_dir(self, tmp_path):
        """get_models_dir creates the folder and returns the path."""
        with patch("app.upscayl_manager.resolve_project_root", return_value=tmp_path):
            from app.upscayl_manager import get_models_dir
            result = get_models_dir()
            assert result == tmp_path / "models" / "upscayl"
            assert result.exists()



class TestModelSizeOnDisk:
    """``size_on_disk_mb`` feeds the cards of the Upscale gallery: without a
    displayed weight, the user can neither weigh up a download nor decide what
    to delete.
    """

    @staticmethod
    def _model():
        from app.upscayl_models import MODELS
        return MODELS[0]

    def test_returns_zero_when_files_are_absent(self, tmp_path):
        assert self._model().size_on_disk_mb(tmp_path) == 0

    def test_sums_both_files_and_rounds_to_megabytes(self, tmp_path):
        model = self._model()
        (tmp_path / f"{model.id}.bin").write_bytes(b"\0" * (3 * 1024 * 1024))
        (tmp_path / f"{model.id}.param").write_bytes(b"\0" * (1024 * 1024))
        assert model.size_on_disk_mb(tmp_path) == 4

    def test_partial_install_still_measures_what_exists(self, tmp_path):
        """A .bin without its .param is not "installed" but still takes disk
        space: the card must be able to report it rather than fail.
        """
        model = self._model()
        (tmp_path / f"{model.id}.bin").write_bytes(b"\0" * (2 * 1024 * 1024))
        assert not model.is_downloaded(tmp_path)
        assert model.size_on_disk_mb(tmp_path) == 2
