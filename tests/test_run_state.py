"""Tests de l'état partagé du run (run_state.py)."""

import pytest

from app.core.run_state import PIPELINE_STEPS, RunState, StepStatus


def test_flag_defaults_all_false():
    state = RunState()
    assert not state.entrainement_apres
    assert not state.nettoyer_apres
    assert not state.exporter_apres
    assert not state.visualiser_apres
    assert not state.undistort_images


def test_setting_flag_notifies_observers_with_key():
    state = RunState()
    seen = []
    state.add_observer(seen.append)
    state.undistort_images = True
    assert seen == ["undistort_images"]


def test_no_notification_when_value_unchanged():
    state = RunState()
    state.entrainement_apres = True
    seen = []
    state.add_observer(seen.append)
    state.entrainement_apres = True  # même valeur → pas de notif (anti-boucle)
    assert seen == []


def test_multiple_observers_stay_synchronized():
    """Deux widgets reflétant le même flag : une seule source, tous notifiés."""
    state = RunState()
    widget_a = {"undistort": None}
    widget_b = {"undistort": None}
    state.add_observer(lambda key: widget_a.__setitem__("undistort", state.undistort_images))
    state.add_observer(lambda key: widget_b.__setitem__("undistort", state.undistort_images))
    state.undistort_images = True
    assert widget_a["undistort"] is True
    assert widget_b["undistort"] is True


def test_observer_exception_does_not_break_others():
    state = RunState()
    seen = []

    def boom(key):
        raise RuntimeError("widget cassé")

    state.add_observer(boom)
    state.add_observer(seen.append)
    state.nettoyer_apres = True  # ne doit pas propager l'exception
    assert seen == ["nettoyer_apres"]


def test_remove_observer():
    state = RunState()
    seen = []
    state.add_observer(seen.append)
    state.remove_observer(seen.append)
    state.exporter_apres = True
    assert seen == []


def test_step_status_lifecycle():
    state = RunState()
    for step in PIPELINE_STEPS:
        assert state.get_status(step) == StepStatus.IDLE
    state.set_status("reconstruction", StepStatus.RUNNING)
    assert state.get_status("reconstruction") == StepStatus.RUNNING
    state.set_status("reconstruction", StepStatus.ERROR)
    assert state.get_status("reconstruction") == StepStatus.ERROR


def test_set_status_accepts_str_value():
    state = RunState()
    state.set_status("export", "done")
    assert state.get_status("export") == StepStatus.DONE


def test_reset_status():
    state = RunState()
    state.set_status("source", StepStatus.DONE)
    state.set_status("export", StepStatus.ERROR)
    state.reset_status()
    assert all(state.get_status(s) == StepStatus.IDLE for s in PIPELINE_STEPS)


def test_unknown_flag_and_step_raise():
    state = RunState()
    with pytest.raises(KeyError):
        state.set_flag("inconnu", True)
    with pytest.raises(KeyError):
        state.set_status("inconnu", StepStatus.DONE)


def test_to_dict_from_dict_roundtrip():
    state = RunState()
    state.entrainement_apres = True
    state.visualiser_apres = True
    data = state.to_dict()
    restored = RunState.from_dict(data)
    assert restored.entrainement_apres
    assert restored.visualiser_apres
    assert not restored.nettoyer_apres


def test_load_dict_ignores_unknown_and_missing_keys():
    state = RunState()
    state.load_dict({"undistort_images": True, "cle_inconnue": 42})
    assert state.undistort_images
    # clés absentes → défaut conservé
    assert not state.nettoyer_apres


def test_load_dict_non_dict_is_noop():
    state = RunState()
    state.load_dict(None)  # ne doit pas lever
    assert not state.undistort_images
