"""Notifications système macOS de fin d'exécution.

Utilise ``NSUserNotificationCenter`` via ``pyobjc-framework-Cocoa`` (déjà une
dépendance du projet — aucune nouvelle dépendance). API historique dépréciée par
Apple mais fonctionnelle sans exécutable signé (contrairement à
``UNUserNotificationCenter``), ce qui convient à une distribution via
``Lancer CorbeauSplat.command``/Homebrew.

Défensif : si pyobjc est absent (CI, autre OS) ou l'API indisponible, ``notify``
retourne ``False`` sans lever — la notification est simplement ignorée.
"""

import logging

logger = logging.getLogger(__name__)


def is_available() -> bool:
    """True si l'API de notification macOS est joignable."""
    try:
        from Foundation import NSUserNotificationCenter
    except Exception:
        return False
    try:
        return NSUserNotificationCenter.defaultUserNotificationCenter() is not None
    except Exception:
        return False


def notify(title: str, message: str) -> bool:
    """Envoie une notification macOS. Retourne True si délivrée, False sinon."""
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
