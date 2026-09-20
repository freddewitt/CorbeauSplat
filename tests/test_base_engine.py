from pathlib import Path

import pytest

from app.core.base_engine import BaseEngine


@pytest.fixture
def engine(tmp_path):
    eng = BaseEngine("test")
    eng.project_root = tmp_path
    return eng


class TestValidatePath:
    def test_valid_path_inside_project_root(self, engine, tmp_path):
        target = tmp_path / "data" / "scene.ply"
        target.parent.mkdir(parents=True)
        target.touch()
        result = engine.validate_path(str(target))
        assert result is not None
        assert result == target.resolve()

    def test_valid_path_inside_desktop(self, engine):
        desktop_target = Path.home() / "Desktop" / "some_corbeausplat_test_file_check.txt"
        desktop_target.parent.mkdir(parents=True, exist_ok=True)
        try:
            desktop_target.touch()
            result = engine.validate_path(str(desktop_target))
            assert result is not None
            assert result == desktop_target.resolve()
        finally:
            desktop_target.unlink(missing_ok=True)

    def test_valid_path_inside_documents(self, engine):
        doc_target = Path.home() / "Documents" / "some_corbeausplat_test_file_check.txt"
        doc_target.parent.mkdir(parents=True, exist_ok=True)
        try:
            doc_target.touch()
            result = engine.validate_path(str(doc_target))
            assert result is not None
            assert result == doc_target.resolve()
        finally:
            doc_target.unlink(missing_ok=True)

    def test_any_absolute_path_is_accepted(self, engine):
        result = engine.validate_path("/opt/corbeausplat_secret")
        assert result is not None
        assert result == Path("/opt/corbeausplat_secret").resolve()

    def test_empty_path_returns_none(self, engine):
        assert engine.validate_path("") is None

    def test_none_path_returns_none(self, engine):
        assert engine.validate_path(None) is None

    def test_nonexistent_path_returns_resolved(self, engine, tmp_path):
        target = tmp_path / "missing" / "file.ply"
        result = engine.validate_path(str(target))
        assert result is not None
        assert result == target.resolve()

    def test_dot_dot_collapsed_returns_resolved(self, engine, tmp_path):
        subdir = tmp_path / "a" / "b"
        subdir.mkdir(parents=True)
        traversal = subdir / ".." / ".." / ".." / ".." / "etc" / "hostname"
        result = engine.validate_path(str(traversal))
        assert result is not None
        assert result == traversal.resolve()

    def test_symlink_inside_root(self, engine, tmp_path):
        real = tmp_path / "real.txt"
        real.touch()
        link = tmp_path / "link.txt"
        link.symlink_to(real)
        result = engine.validate_path(str(link))
        assert result is not None


class TestPathExists:
    def test_existing_file(self, engine, tmp_path):
        target = tmp_path / "ok.txt"
        target.touch()
        assert engine.path_exists(str(target)) is True

    def test_nonexistent_file(self, engine, tmp_path):
        target = tmp_path / "nope.txt"
        assert engine.path_exists(str(target)) is False

    def test_nonexistent_path_outside_project(self, engine):
        assert engine.path_exists("/tmp/corbeausplat_fake") is False

    def test_existing_path_outside_project_is_accepted(self, engine, tmp_path):
        """Existence is the whole contract: being outside the project is not a rejection.

        This is what the old `is_safe_path` name hid. The user routinely picks
        sources on the Desktop or an external volume, so a containment check
        here would reject legitimate input.
        """
        outside = tmp_path / "outside.txt"
        outside.touch()
        assert engine.path_exists(str(outside)) is True

    def test_empty_string(self, engine):
        assert engine.path_exists("") is False
