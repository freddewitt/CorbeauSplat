import json
import logging

from app.core.system import resolve_project_root

logger = logging.getLogger(__name__)

DEFAULT_LANG = "en"


def _locales_dir():
    return resolve_project_root() / "assets" / "locales"


def is_known_lang(lang_code):
    """True if ``lang_code`` is a plain code with a matching locale file.

    The isalnum() guard keeps a config-supplied value from escaping the
    locales directory (e.g. "../../secrets").
    """
    if not isinstance(lang_code, str) or not lang_code.isalnum():
        return False
    return (_locales_dir() / f"{lang_code}.json").exists()


class LanguageManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.current_lang = DEFAULT_LANG
            cls._instance._translations = {}
            cls._instance._observers = []
            cls._instance.load_config()
            cls._instance._load_translations()
        return cls._instance

    def add_observer(self, callback):
        """Add a callback to be notified when language changes"""
        if callback not in self._observers:
            self._observers.append(callback)

    def _load_translations(self):
        """Load translations from JSON for the current language"""
        try:
            locales_dir = resolve_project_root() / "assets" / "locales"
            lang_path = locales_dir / f"{self.current_lang}.json"

            # Fallback to English if current lang doesn't exist
            if not lang_path.exists():
                lang_path = locales_dir / "en.json"

            # Final fallback to French if nothing found (core default)
            if not lang_path.exists():
                lang_path = locales_dir / "fr.json"

            if lang_path.exists():
                with open(lang_path, encoding="utf-8") as f:
                    self._translations = json.load(f)
            else:
                self._translations = {}
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Error loading translations: %s", e)
            self._translations = {}

    def load_config(self):
        config_file = resolve_project_root() / "config.json"
        try:
            if config_file.exists():
                with open(config_file) as f:
                    config = json.load(f)
                    saved = config.get("language")
                    if is_known_lang(saved):
                        self.current_lang = saved
                    else:
                        logger.warning(
                            "Langue invalide dans %s (%r) — repli sur %s",
                            config_file, saved, DEFAULT_LANG,
                        )
                        self.current_lang = DEFAULT_LANG
                    logger.info(
                        "Langue chargée au démarrage : %s (depuis %s, clé 'language'=%r)",
                        self.current_lang, config_file, saved,
                    )
            else:
                logger.info(
                    "Langue au démarrage : %s (défaut — %s introuvable)",
                    self.current_lang, config_file,
                )
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(
                "Could not load language config from %s: %s — repli sur %s",
                config_file, e, self.current_lang,
            )

    def save_config(self):
        try:
            config_file = resolve_project_root() / "config.json"
            config = {}
            if config_file.exists():
                with open(config_file) as f:
                    existing = json.load(f)
                    if isinstance(existing, dict):
                        config = existing
            config["language"] = self.current_lang
            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)
            logger.info("Langue enregistrée : %s (dans %s)", self.current_lang, config_file)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Could not save language config to %s: %s", config_file, e)

    def set_language(self, lang_code):
        if not is_known_lang(lang_code):
            logger.warning("Changement de langue ignoré : code inconnu %r", lang_code)
            return
        self.current_lang = lang_code
        self._load_translations() # Reload on change
        self.save_config()
        for cb in self._observers:
            try:
                cb()
            except Exception:
                logger.exception("Error notifying language observer: %s", cb)

    def tr(self, key, *args):
        text = self._translations.get(key)
        if text is None:
            if args:
                text = str(args[0])
                args = args[1:]
            else:
                text = key
        if args:
            try:
                text = text.format(*args)
            except (IndexError, KeyError) as e:
                logger.debug("i18n format error for key '%s': %s", key, e)
        return text

# Global instance convenience
_lm = LanguageManager()

def tr(key, *args):
    return _lm.tr(key, *args)

def get_current_lang():
    return _lm.current_lang

def set_language(lang_code):
    _lm.set_language(lang_code)

def add_language_observer(callback):
    _lm.add_observer(callback)
