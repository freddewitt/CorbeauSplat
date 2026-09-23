"""macOS system notifications on run completion.

Uses ``NSUserNotificationCenter`` through ``pyobjc-framework-Cocoa`` (already a
project dependency — no new one). A historical API, deprecated by Apple but
working without a signed executable (unlike ``UNUserNotificationCenter``), which
suits a distribution through ``CorbeauSplat.command``/Homebrew.

Defensive: when pyobjc is missing (CI, another OS) or the API is unavailable,
``notify`` returns ``False`` without raising — the notification is simply
skipped.
"""

import json
import logging

from .system import resolve_project_root

logger = logging.getLogger(__name__)

# config.json key holding the "end-of-run notifications" toggle (audit L6-01:
# the setting used to live only in memory and reset to off on every launch).
CONFIG_KEY = "notifications_enabled"


def get_saved_enabled(default: bool = False) -> bool:
    """Read the notifications toggle from config.json (same idiom as the theme)."""
    try:
        config_file = resolve_project_root() / "config.json"
        if config_file.exists():
            with open(config_file) as f:
                data = json.load(f)
            if isinstance(data, dict):
                return bool(data.get(CONFIG_KEY, default))
    except (OSError, json.JSONDecodeError):
        pass
    return default


def save_enabled(enabled: bool) -> None:
    """Persist the notifications toggle to config.json, preserving other keys."""
    try:
        config_file = resolve_project_root() / "config.json"
        config = {}
        if config_file.exists():
            with open(config_file) as f:
                existing = json.load(f)
            if isinstance(existing, dict):
                config = existing
        config[CONFIG_KEY] = bool(enabled)
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
    except (OSError, json.JSONDecodeError):
        logger.warning("Notifications: impossible d'écrire le réglage dans config.json")


def is_available() -> bool:
    """True when the macOS notification API is reachable."""
    try:
        from Foundation import NSUserNotificationCenter
    except Exception:
        return False
    try:
        return NSUserNotificationCenter.defaultUserNotificationCenter() is not None
    except Exception:
        return False


def notify(title: str, message: str) -> bool:
    """Send a macOS notification. Returns True when delivered, False otherwise."""
    try:
        from Foundation import NSUserNotification, NSUserNotificationCenter
    except Exception:
        logger.debug("Notifications indisponibles (pyobjc/Foundation absent)")
        return False
    try:
        note = NSUserNotification.alloc().init()
        note.setTitle_(str(title))
        note.setInformativeText_(str(message))
        center = NSUserNotificationCenter.defaultUserNotificationCenter()
        if center is None:
            return False
        center.deliverNotification_(note)
        return True
    except Exception:
        logger.exception("Échec de l'envoi de la notification")
        return False
