"""Sauvegarde/chargement de configurations *nommées et réutilisables* de la
chaîne complète (icônes Charger/Sauvegarder du top bar).

Distinct de ``SessionManager`` (qui persiste l'unique session GUI courante dans
``config.json``) : ici plusieurs configurations nommées, réutilisables, chacune
dans son fichier sous ``configs/``.

La sérialisation par section réutilise le contrat ``to_dict``/``from_dict`` déjà
en place (``ColmapParams``, ``BrushParams``, ``RunState``) plutôt que de
dupliquer une logique parallèle. ``from_dict`` étant tolérant aux clés
manquantes/inconnues, une config sauvegardée par une version antérieure se
recharge sans casser.
"""

import json
import logging
from dataclasses import asdict, dataclass, field

from .params import ColmapParams
from .run_state import RunState
from .system import resolve_project_root

logger = logging.getLogger(__name__)

CONFIG_VERSION = 1


def configs_dir():
    """Dossier des configurations nommées (créé à la demande)."""
    d = resolve_project_root() / "configs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def is_safe_config_name(name: str) -> bool:
    """Même règle que la sanitisation du nom de projet (``engine.py``) : pas de
    ``..``, ``/`` ni ``\\``, et non vide."""
    if not name or not name.strip():
        return False
    return ".." not in name and "/" not in name and "\\" not in name


@dataclass
class ChainConfig:
    """Configuration complète de la chaîne, sérialisable vers un fichier nommé."""

    version: int = CONFIG_VERSION
    source: dict = field(default_factory=dict)     # input_path, output_path, project_name, fps…
    colmap: dict = field(default_factory=dict)     # ColmapParams.to_dict()
    brush: dict = field(default_factory=dict)      # BrushParams.to_dict()
    cleaning: dict = field(default_factory=dict)   # intensité, opacity_min, scale_pct, outlier_pct
    export: dict = field(default_factory=dict)     # format cible, scale…
    flags: dict = field(default_factory=dict)      # RunState.to_dict()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ChainConfig":
        """Reconstruit une config depuis un dict, tolérant aux sections
        manquantes et aux versions antérieures."""
        if not isinstance(data, dict):
            return cls()
        data = _migrate(dict(data))
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    # Helpers typés : rechargent des objets à partir des sections, en s'appuyant
    # sur la tolérance de leurs from_dict respectifs.
    def colmap_params(self) -> ColmapParams:
        return ColmapParams.from_dict(self.colmap or {})

    def run_state(self) -> RunState:
        return RunState.from_dict(self.flags or {})


def _migrate(data: dict) -> dict:
    """Point d'extension pour les migrations de schéma futures. Aujourd'hui
    identité (version 1). Les versions inconnues sont chargées au mieux."""
    return data


def save_config(name: str, config: ChainConfig | dict) -> "object":
    """Écrit une configuration nommée. Retourne le chemin du fichier."""
    if not is_safe_config_name(name):
        raise ValueError(f"Nom de configuration invalide: {name!r}")
    data = config.to_dict() if isinstance(config, ChainConfig) else dict(config)
    data.setdefault("version", CONFIG_VERSION)
    path = configs_dir() / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def load_config(name: str) -> ChainConfig:
    """Charge une configuration nommée. Lève ``FileNotFoundError`` si absente."""
    if not is_safe_config_name(name):
        raise ValueError(f"Nom de configuration invalide: {name!r}")
    path = configs_dir() / f"{name}.json"
    with open(path, encoding="utf-8") as f:
        return ChainConfig.from_dict(json.load(f))


def list_configs() -> list:
    """Noms des configurations disponibles (triés)."""
    try:
        return sorted(p.stem for p in configs_dir().glob("*.json"))
    except OSError as e:
        logger.warning("Impossible de lister les configurations: %s", e)
        return []


def delete_config(name: str) -> bool:
    """Supprime une configuration nommée. Retourne True si un fichier a été retiré."""
    if not is_safe_config_name(name):
        raise ValueError(f"Nom de configuration invalide: {name!r}")
    path = configs_dir() / f"{name}.json"
    if path.exists():
        path.unlink()
        return True
    return False
