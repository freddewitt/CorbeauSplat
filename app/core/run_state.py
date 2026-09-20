"""Shared state of the pipeline run — single source of truth for duplicated flags.

Several places in the interface (Source, Reconstruction, Entraînement, OUTILS
modules) show and change the same auto-chaining flags ("Entraînement après",
"Nettoyer après", etc.) as well as ``undistort_images``. To avoid the drift that
historically scattered ``undistort_images``/``filter_blurry``/``blur_factor``
across tabs, every flag lives here **once**: the widgets subscribe to it and
mirror it. Same principle for the project name (a text field shown both in the
Source panel and in the top bar).

The observation mechanism deliberately reuses the same idiom as
``LanguageManager`` (``add_observer`` / best-effort notification with logging)
rather than inventing a second one.
"""

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class StepStatus(str, Enum):
    """Run status of a rail step (drives the tick / spinner / red icon)."""

    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


# PIPELINE steps, in rail order. 4DGS stops at source+reconstruction,
# Sharp skips training — handled on the UI side, not here (this module stays agnostic).
PIPELINE_STEPS = (
    "source",
    "extraction360",
    "upscale",
    "reconstruction",
    "entrainement",
    "nettoyage",
    "export",
    "visualiser",
)

# Chaining flags + undistort, each a single property mirrored by several
# widgets. Defaults aligned on the current behaviour.
_FLAG_DEFAULTS = {
    "source_360": False,
    "upscaler_avant": False,
    "entrainement_apres": False,
    "nettoyer_apres": False,
    "exporter_apres": False,
    "visualiser_apres": False,
    "undistort_images": False,
}

# Shared text fields (same principle as the flags, but with a str value).
# The project name is shown in two places (Source panel + top bar):
# it lives here once so it stays in sync in real time.
_FIELD_DEFAULTS = {
    "project_name": "",
}


class RunState:
    """Observable shared state object.

    - A flag only notifies when its value actually changes (avoids feedback
      loops when an observing widget rewrites itself).
    - Observers are called with the changed key (flag or step name), so each
      widget can react only to what concerns it.
    """

    def __init__(self) -> None:
        self._flags = dict(_FLAG_DEFAULTS)
        self._fields = dict(_FIELD_DEFAULTS)
        self._status = dict.fromkeys(PIPELINE_STEPS, StepStatus.IDLE)
        self._observers: list = []

    # ── Observation ──────────────────────────────────────────────────────────
    def add_observer(self, callback) -> None:
        """Register a ``callback(key: str)`` notified on every change."""
        if callback not in self._observers:
            self._observers.append(callback)

    def remove_observer(self, callback) -> None:
        if callback in self._observers:
            self._observers.remove(callback)

    def _notify(self, key: str) -> None:
        for cb in list(self._observers):
            try:
                cb(key)
            except Exception:
                logger.exception("Error notifying run-state observer: %s", cb)

    # ── Flags ────────────────────────────────────────────────────────────────
    def get_flag(self, name: str) -> bool:
        return self._flags[name]

    def set_flag(self, name: str, value: bool) -> None:
        if name not in self._flags:
            raise KeyError(f"Drapeau inconnu: {name}")
        value = bool(value)
        if self._flags[name] != value:
            self._flags[name] = value
            self._notify(name)

    # ── Text fields ──────────────────────────────────────────────────────────
    def get_field(self, name: str) -> str:
        return self._fields[name]

    def set_field(self, name: str, value: str) -> None:
        if name not in self._fields:
            raise KeyError(f"Champ inconnu: {name}")
        value = "" if value is None else str(value)
        if self._fields[name] != value:
            self._fields[name] = value
            self._notify(name)

    @property
    def project_name(self) -> str:
        return self._fields["project_name"]

    @project_name.setter
    def project_name(self, value: str) -> None:
        self.set_field("project_name", value)

    @property
    def source_360(self) -> bool:
        return self._flags["source_360"]

    @source_360.setter
    def source_360(self, value: bool) -> None:
        self.set_flag("source_360", value)

    @property
    def upscaler_avant(self) -> bool:
        return self._flags["upscaler_avant"]

    @upscaler_avant.setter
    def upscaler_avant(self, value: bool) -> None:
        self.set_flag("upscaler_avant", value)

    @property
    def entrainement_apres(self) -> bool:
        return self._flags["entrainement_apres"]

    @entrainement_apres.setter
    def entrainement_apres(self, value: bool) -> None:
        self.set_flag("entrainement_apres", value)

    @property
    def nettoyer_apres(self) -> bool:
        return self._flags["nettoyer_apres"]

    @nettoyer_apres.setter
    def nettoyer_apres(self, value: bool) -> None:
        self.set_flag("nettoyer_apres", value)

    @property
    def exporter_apres(self) -> bool:
        return self._flags["exporter_apres"]

    @exporter_apres.setter
    def exporter_apres(self, value: bool) -> None:
        self.set_flag("exporter_apres", value)

    @property
    def visualiser_apres(self) -> bool:
        return self._flags["visualiser_apres"]

    @visualiser_apres.setter
    def visualiser_apres(self, value: bool) -> None:
        self.set_flag("visualiser_apres", value)

    @property
    def undistort_images(self) -> bool:
        return self._flags["undistort_images"]

    @undistort_images.setter
    def undistort_images(self, value: bool) -> None:
        self.set_flag("undistort_images", value)

    # ── Step status (drives the rail) ────────────────────────────────────────
    def get_status(self, step: str) -> StepStatus:
        return self._status[step]

    def set_status(self, step: str, status: StepStatus) -> None:
        if step not in self._status:
            raise KeyError(f"Étape inconnue: {step}")
        status = StepStatus(status)
        if self._status[step] != status:
            self._status[step] = status
            self._notify(step)

    def reset_status(self) -> None:
        """Reset every step to IDLE (new run). Notifies each change."""
        for step in PIPELINE_STEPS:
            self.set_status(step, StepStatus.IDLE)

    # ── Serialisation (flags only — the status is transient) ──────────────────
    def to_dict(self) -> dict:
        return dict(self._flags)

    def load_dict(self, data: dict) -> None:
        """Apply the flags of a dict (unknown keys ignored, missing ones left at
        their default). Notifies every flag actually changed.
        """
        if not isinstance(data, dict):
            return
        for name in _FLAG_DEFAULTS:
            if name in data:
                self.set_flag(name, data[name])

    @classmethod
    def from_dict(cls, data: dict) -> "RunState":
        state = cls()
        state.load_dict(data)
        return state
