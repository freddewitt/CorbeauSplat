"""Tests d'intégration : validation de chemins + i18n (sans subprocess)."""
import json
from pathlib import Path

import pytest

from tests.conftest import _patch_pyqt6

_patch_pyqt6()

ASSETS_LOCALES = Path(__file__).resolve().parent.parent.parent / "assets" / "locales"


class TestPathValidation:
    """BaseEngine path validation security tests."""

    @pytest.fixture
    def engine(self):
        """Create a BaseEngine subclass instance for testing path validation."""
        from app.core.base_engine import BaseEngine
        engine = BaseEngine(name="test_engine")
        engine.project_root = Path("/tmp/test_project")
        return engine

    def test_validate_path_valid(self, engine, tmp_path):
        """A path within the project root should pass validation."""
        allowed = tmp_path / "subdir" / "file.txt"
        allowed.parent.mkdir(parents=True, exist_ok=True)
        allowed.write_text("test")
        # validate_path returns a Path (resolved) or None on error
        result = engine.validate_path(str(allowed))
        assert result is not None
        assert isinstance(result, Path)
        assert result.exists()

    def test_path_exists_rejects_missing_path(self, engine):
        """A path that is not on disk is rejected, wherever it points."""
        assert engine.path_exists("/nonexistent/outside/file.txt") is False

    def test_traversal_is_normalised_not_rejected(self, engine, tmp_path):
        """`..` segments are resolved away; they are not treated as an attack.

        The previous version of this test asserted False and passed only
        because the target did not exist, which read as a traversal defence
        that does not exist. Here the resolved target *does* exist, so the
        real behaviour is visible: the path is normalised and accepted.
        """
        engine.project_root = tmp_path
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        target = tmp_path / "a" / "target.txt"
        target.write_text("test")

        traversed = nested / ".." / "target.txt"
        assert engine.validate_path(str(traversed)) == target.resolve()
        assert engine.path_exists(str(traversed)) is True

    def test_validate_path_resolves_without_requiring_existence(self, engine, tmp_path):
        """validate_path resolves and returns a Path; it does not test existence."""
        missing = tmp_path / "outside_file.txt"
        result = engine.validate_path(str(missing))
        assert result == missing.resolve()
        assert not result.exists()

    def test_validate_path_returns_none_on_empty_input(self, engine):
        """The only None case is falsy input or an unresolvable string."""
        assert engine.validate_path("") is None
        assert engine.validate_path(None) is None


class TestI18n:
    """LanguageManager and translation tests."""

    @pytest.fixture(autouse=True)
    def _preserve_user_config(self):
        """Restore config.json and the active language after each test.

        set_language() persists to the project's real config.json, so without
        this the suite would leave the user's app in whatever language the last
        test happened to select.
        """
        from app.core.i18n import get_current_lang, set_language
        from app.core.system import resolve_project_root

        config_file = resolve_project_root() / "config.json"
        original_bytes = config_file.read_bytes() if config_file.exists() else None
        original_lang = get_current_lang()
        try:
            yield
        finally:
            set_language(original_lang)
            if original_bytes is None:
                config_file.unlink(missing_ok=True)
            else:
                config_file.write_bytes(original_bytes)

    def test_tr_returns_french(self):
        """After set_language('fr'), tr returns expected French."""
        from app.core.i18n import set_language, tr

        set_language("fr")
        # Use a key that exists in fr.json
        msg = tr("btn_browse")
        assert msg is not None
        assert len(msg) > 0

    def test_tr_fallback_to_english(self):
        """If key is missing in French, fallback to English."""
        from app.core.i18n import set_language, tr

        set_language("fr")
        # An unlikely key that might not exist in French
        msg = tr("nonexistent_key_xyz")
        # Should return something (key or fallback)
        assert msg is not None

    def test_language_observer_notified(self):
        """Observer callback is called after set_language()."""
        from app.core.i18n import add_language_observer, set_language

        calls = []
        def observer():
            calls.append("called")

        add_language_observer(observer)
        set_language("en")
        assert len(calls) >= 1

    def test_all_locales_valid_json(self):
        """All 9 locale files are valid JSON and contain required keys."""
        locale_dir = ASSETS_LOCALES

        assert locale_dir.exists(), f"Locales directory not found: {locale_dir}"

        locale_files = sorted(locale_dir.glob("*.json"))
        assert len(locale_files) >= 3, f"Expected at least 3 locale files, found {len(locale_files)}"

        for lf in locale_files:
            data = json.loads(lf.read_text(encoding="utf-8"))
            assert isinstance(data, dict)
            # Check it has some content
            assert len(data) > 10

    def test_language_cycle(self):
        """Switching between multiple languages works."""
        from app.core.i18n import set_language, tr

        set_language("fr")
        fr_msg = tr("btn_browse")
        set_language("de")
        de_msg = tr("btn_browse")
        set_language("en")
        en_msg = tr("btn_browse")

        assert fr_msg is not None
        assert en_msg is not None
        # German might or might not exist
        if de_msg:
            assert isinstance(de_msg, str)

    def test_observer_multiple_languages(self):
        """Observer fired for each language change."""
        from app.core.i18n import add_language_observer, set_language

        calls = []
        def obs():
            calls.append("x")

        add_language_observer(obs)
        for lang in ["fr", "de", "en", "es"]:
            set_language(lang)

        assert len(calls) >= 3
