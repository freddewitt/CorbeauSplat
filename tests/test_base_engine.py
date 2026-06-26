import os
from pathlib import Path
from unittest.mock import MagicMock

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

    def test_valid_path_inside_home(self, engine):
        home_target = Path.home() / "some_corbeausplat_test_file_check.txt"
        try:
            home_target.touch()
            result = engine.validate_path(str(home_target))
            assert result is not None
            assert result == home_target.resolve()
        finally:
            home_target.unlink(missing_ok=True)

    def test_traversal_attempt_blocked(self, engine, tmp_path):
        malicious = tmp_path / ".." / ".." / ".." / "etc" / "passwd"
        result = engine.validate_path(str(malicious))
        assert result is None

    def test_absolute_path_outside_project_allowed(self, engine):
        # Desktop tool: user-chosen absolute paths (any drive/folder) are allowed.
        result = engine.validate_path("/opt/corbeausplat_output")
        assert result == Path("/opt/corbeausplat_output").resolve()

    def test_empty_path_returns_none(self, engine):
        assert engine.validate_path("") is None

    def test_none_path_returns_none(self, engine):
        assert engine.validate_path(None) is None

    def test_nonexistent_path_inside_root_returns_resolved(self, engine, tmp_path):
        target = tmp_path / "missing" / "file.ply"
        result = engine.validate_path(str(target))
        assert result is not None
        assert result == target.resolve()

    def test_dot_dot_collapsed(self, engine, tmp_path):
        subdir = tmp_path / "a" / "b"
        subdir.mkdir(parents=True)
        traversal = subdir / ".." / ".." / ".." / ".." / "etc" / "hostname"
        result = engine.validate_path(str(traversal))
        assert result is None

    def test_symlink_inside_root(self, engine, tmp_path):
        real = tmp_path / "real.txt"
        real.touch()
        link = tmp_path / "link.txt"
        link.symlink_to(real)
        result = engine.validate_path(str(link))
        assert result is not None


class TestIsSafePath:
    def test_existing_file_inside_root(self, engine, tmp_path):
        target = tmp_path / "ok.txt"
        target.touch()
        assert engine.is_safe_path(str(target)) is True

    def test_nonexistent_file(self, engine, tmp_path):
        target = tmp_path / "nope.txt"
        assert engine.is_safe_path(str(target)) is False

    def test_path_outside_root(self, engine):
        assert engine.is_safe_path("/tmp/corbeausplat_fake") is False

    def test_empty_string(self, engine):
        assert engine.is_safe_path("") is False
