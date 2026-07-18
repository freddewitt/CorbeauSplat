"""Tests du binding RunState ↔ case à cocher (source de vérité unique).

Utilise un faux widget (duck-typing) pour tester la logique sans Qt, donc
exécutable sous le mock PySide6.
"""

from app.core.run_state import RunState
from app.gui.run_state_binding import bind_flag_checkbox


class _FakeSignal:
    def __init__(self):
        self._cbs = []

    def connect(self, cb):
        self._cbs.append(cb)

    def emit(self, *args):
        for cb in list(self._cbs):
            cb(*args)


class _FakeCheckBox:
    """Imite QCheckBox : setChecked n'émet toggled que sur changement réel et
    hors blockSignals."""

    def __init__(self):
        self._checked = False
        self._blocked = False
        self.toggled = _FakeSignal()

    def isChecked(self):
        return self._checked

    def setChecked(self, value):
        value = bool(value)
        if value != self._checked:
            self._checked = value
            if not self._blocked:
                self.toggled.emit(value)

    def blockSignals(self, blocked):
        self._blocked = bool(blocked)

    def user_click(self, value):
        """Simule un clic utilisateur (Qt émettrait toggled)."""
        self.setChecked(value)


def test_initial_value_synced_from_state():
    rs = RunState()
    rs.entrainement_apres = True
    chk = _FakeCheckBox()
    bind_flag_checkbox(chk, rs, "entrainement_apres")
    assert chk.isChecked() is True


def test_widget_toggle_updates_state():
    rs = RunState()
    chk = _FakeCheckBox()
    bind_flag_checkbox(chk, rs, "nettoyer_apres")
    chk.user_click(True)
    assert rs.nettoyer_apres is True


def test_two_checkboxes_stay_in_sync():
    """Deux cases bindées au même drapeau : toggler l'une met l'autre à jour."""
    rs = RunState()
    a, b = _FakeCheckBox(), _FakeCheckBox()
    bind_flag_checkbox(a, rs, "undistort_images")
    bind_flag_checkbox(b, rs, "undistort_images")
    a.user_click(True)
    assert rs.undistort_images is True
    assert b.isChecked() is True
    b.user_click(False)
    assert rs.undistort_images is False
    assert a.isChecked() is False


def test_state_change_reflects_in_widget():
    rs = RunState()
    chk = _FakeCheckBox()
    bind_flag_checkbox(chk, rs, "visualiser_apres")
    rs.visualiser_apres = True  # changement côté état
    assert chk.isChecked() is True


def test_no_infinite_loop_and_no_spurious_state_churn():
    rs = RunState()
    chk = _FakeCheckBox()
    bind_flag_checkbox(chk, rs, "exporter_apres")
    seen = []
    rs.add_observer(seen.append)
    chk.user_click(True)
    # une seule notification pour ce drapeau (pas de rebond)
    assert seen.count("exporter_apres") == 1
