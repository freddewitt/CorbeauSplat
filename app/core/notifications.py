"""macOS system notifications on run completion.

Uses ``NSUserNotificationCenter`` through ``pyobjc-framework-Cocoa`` (already a
project dependency — no new one). A historical API, deprecated by Apple but
working without a signed executable (unlike ``UNUserNotificationCenter``), which
suits a distribution through ``CorbeauSplat.command``/Homebrew.

Defensive: when pyobjc is missing (CI, another OS) or the API is unavailable,
``notify`` returns ``False`` without raising — the notification is simply
skipped.
"""

import logging

logger = logging.getLogger(__name__)


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
