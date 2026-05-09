import json
import logging
import os
from pathlib import Path
from app.core.system import resolve_project_root

logger = logging.getLogger(__name__)

class LanguageManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LanguageManager, cls).__new__(cls)
            cls._instance.current_lang = "fr" # Default
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
                with open(lang_path, "r", encoding="utf-8") as f:
                    self._translations = json.load(f)
            else:
                self._translations = {}
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Error loading translations: %s", e)
            self._translations = {}

    def load_config(self):
        try:
            config_file = resolve_project_root() / "config.json"
            if config_file.exists():
                with open(config_file, "r") as f:
                    config = json.load(f)
                    self.current_lang = config.get("language", "fr")
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Could not load language config: %s", e)

    def save_config(self):
        try:
            config_file = resolve_project_root() / "config.json"
            config = {}
            if config_file.exists():
                with open(config_file, "r") as f:
                    existing = json.load(f)
                    if isinstance(existing, dict):
                        config = existing
            config["language"] = self.current_lang
            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Could not save language config: %s", e)

    def set_language(self, lang_code):
        self.current_lang = lang_code
        self._load_translations() # Reload on change
        self.save_config()
        for cb in self._observers:
            try:
                cb()
            except Exception:
                pass

    def tr(self, key, *args):
        text = self._translations.get(key, key)
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
