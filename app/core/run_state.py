"""État partagé du run pipeline — source de vérité unique des flags dupliqués.

Plusieurs endroits de l'interface (Source, Reconstruction, Entraînement, modules
OUTILS) affichent et modifient les mêmes drapeaux de chaînage automatique
(« Entraînement après », « Nettoyer après », etc.) ainsi que ``undistort_images``.
Pour éviter la dérive qui a produit l'éclatement historique de
``undistort_images``/``filter_blurry``/``blur_factor`` entre onglets, chaque
drapeau vit ici **une seule fois** : les widgets s'y abonnent et le reflètent.
Même principe pour le nom de projet (champ texte affiché dans le panneau
Source et dans la top bar).

Le mécanisme d'observation reprend volontairement le même idiome que
``LanguageManager`` (``add_observer``/notification best-effort avec log) plutôt
que d'en inventer un second.
"""

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class StepStatus(str, Enum):
    """État d'exécution d'une étape du rail (pilote coche / spinner / icône rouge)."""

    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


# Étapes PIPELINE, dans l'ordre du rail. 4DGS tronque à source+reconstruction,
# Sharp saute l'entraînement — géré côté UI, pas ici (ce module reste agnostique).
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

# Drapeaux de chaînage + undistort, chacun une propriété unique reflétée par
# plusieurs widgets. Valeurs par défaut alignées sur le comportement actuel.
_FLAG_DEFAULTS = {
    "source_360": False,
    "upscaler_avant": False,
    "entrainement_apres": False,
    "nettoyer_apres": False,
    "exporter_apres": False,
    "visualiser_apres": False,
    "undistort_images": False,
}

# Champs texte partagés (même principe que les drapeaux, mais valeur str).
# Le nom de projet est affiché à deux endroits (panneau Source + top bar) :
# il vit ici une seule fois pour rester synchronisé en temps réel.
_FIELD_DEFAULTS = {
    "project_name": "",
}


class RunState:
    """Objet d'état partagé observable.

    - Un drapeau ne notifie que s'il change réellement de valeur (évite les
      boucles de rétroaction quand un widget observateur se ré-écrit lui-même).
    - Les observateurs sont appelés avec la clé modifiée (nom du drapeau ou de
      l'étape), permettant à chaque widget de ne réagir qu'à ce qui le concerne.
    """

    def __init__(self) -> None:
        self._flags = dict(_FLAG_DEFAULTS)
        self._fields = dict(_FIELD_DEFAULTS)
        self._status = dict.fromkeys(PIPELINE_STEPS, StepStatus.IDLE)
        self._observers: list = []

    # ── Observation ──────────────────────────────────────────────────────────
    def add_observer(self, callback) -> None:
        """Enregistre un callback ``callback(key: str)`` notifié à chaque changement."""
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

    # ── Drapeaux ─────────────────────────────────────────────────────────────
    def get_flag(self, name: str) -> bool:
        return self._flags[name]

    def set_flag(self, name: str, value: bool) -> None:
        if name not in self._flags:
            raise KeyError(f"Drapeau inconnu: {name}")
        value = bool(value)
        if self._flags[name] != value:
            self._flags[name] = value
            self._notify(name)

    # ── Champs texte ─────────────────────────────────────────────────────────
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

    # ── Statut des étapes (pilote le rail) ───────────────────────────────────
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
        """Remet toutes les étapes à IDLE (nouveau run). Notifie chaque changement."""
        for step in PIPELINE_STEPS:
            self.set_status(step, StepStatus.IDLE)

    # ── Sérialisation (drapeaux uniquement — le statut est transitoire) ───────
    def to_dict(self) -> dict:
        return dict(self._flags)

    def load_dict(self, data: dict) -> None:
        """Applique les drapeaux d'un dict (clés inconnues ignorées, absentes
        laissées à leur défaut). Notifie chaque drapeau réellement modifié."""
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
