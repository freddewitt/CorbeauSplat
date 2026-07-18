"""Presets Brush personnalisés, persistés et nommés par l'utilisateur.

Complète les presets intégrés (``BRUSH_PRESETS``, Strategy pattern existant côté
CLI) sans les dupliquer ni les déplacer : ce module ne gère que les presets
*utilisateur*. Le code appelant fusionne les deux via :func:`merge_presets` en
passant les presets intégrés en argument, ce qui évite une dépendance
``core → cli`` (couche inversée).

Stockage : fichier JSON dédié ``brush_presets.json`` à la racine, voisin de
``config.json`` géré par ``SessionManager``.
"""

import json
import logging

from .config_io import is_safe_config_name
from .system import resolve_project_root

logger = logging.getLogger(__name__)


def _store_path():
    return resolve_project_root() / "brush_presets.json"


def load_user_presets() -> dict:
    """Retourne le dict ``{nom: params}`` des presets utilisateur (vide si aucun
    ou fichier illisible)."""
    path = _store_path()
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Presets Brush illisibles (%s): %s", path, e)
        return {}


def _write(presets: dict) -> None:
    with open(_store_path(), "w", encoding="utf-8") as f:
        json.dump(presets, f, indent=2, ensure_ascii=False)


def save_user_preset(name: str, params: dict) -> None:
    """Enregistre (ou écrase) un preset utilisateur nommé."""
    if not is_safe_config_name(name):
        raise ValueError(f"Nom de preset invalide: {name!r}")
    presets = load_user_presets()
    presets[name] = dict(params)
    _write(presets)


def delete_user_preset(name: str) -> bool:
    """Supprime un preset utilisateur. Retourne True si retiré."""
    presets = load_user_presets()
    if name in presets:
        del presets[name]
        _write(presets)
        return True
    return False


def merge_presets(builtins: dict) -> dict:
    """Fusionne presets intégrés + utilisateur (l'utilisateur l'emporte en cas de
    collision de nom). ``builtins`` est passé par l'appelant (ex. ``BRUSH_PRESETS``)
    pour ne pas inverser la dépendance core→cli."""
    merged = dict(builtins or {})
    merged.update(load_user_presets())
    return merged
