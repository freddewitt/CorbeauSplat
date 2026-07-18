"""Tests du module de notifications macOS (dégradation propre)."""

import builtins

from app.core import notifications


def test_notify_returns_false_without_foundation(monkeypatch):
    """Si Foundation (pyobjc) est absent, notify ne lève pas et retourne False."""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "Foundation":
            raise ImportError("no pyobjc in this env")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert notifications.notify("Titre", "Message") is False
    assert notifications.is_available() is False


def test_notify_delivers_when_foundation_present(monkeypatch):
    """Avec un faux Foundation, notify construit et délivre la notification."""
    import sys
    import types

    delivered = {}

    class _Note:
        @classmethod
        def alloc(cls):
            return cls()

        def init(self):
            return self

        def setTitle_(self, t):
            delivered["title"] = t

        def setInformativeText_(self, m):
            delivered["msg"] = m

    class _Center:
        @classmethod
        def defaultUserNotificationCenter(cls):
            return cls()

        def deliverNotification_(self, note):
            delivered["sent"] = True

    fake = types.ModuleType("Foundation")
    fake.NSUserNotification = _Note
    fake.NSUserNotificationCenter = _Center
    monkeypatch.setitem(sys.modules, "Foundation", fake)

    assert notifications.notify("Fini", "Run terminé") is True
    assert delivered == {"title": "Fini", "msg": "Run terminé", "sent": True}
