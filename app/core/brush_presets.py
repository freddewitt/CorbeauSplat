"""Custom Brush presets, persisted and named by the user.

Complements the built-in presets (``BRUSH_PRESETS``, the existing Strategy
pattern on the CLI side) without duplicating or moving them: this module only
handles *user* presets. The calling code merges both through
:func:`merge_presets`, passing the built-in presets as an argument, which avoids
a ``core → cli`` dependency (an inverted layer).

Storage: a dedicated ``brush_presets.json`` file at the root, next to the
``config.json`` managed by ``SessionManager``.
"""

import json
import logging

from .config_io import is_safe_config_name
from .system import resolve_project_root

logger = logging.getLogger(__name__)


def _store_path():
    return resolve_project_root() / "brush_presets.json"


def load_user_presets() -> dict:
    """Return the ``{name: params}`` dict of the user presets (empty when there
    is none, or when the file is unreadable)."""
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
    """Save (or overwrite) a named user preset."""
    if not is_safe_config_name(name):
        raise ValueError(f"Nom de preset invalide: {name!r}")
    presets = load_user_presets()
    presets[name] = dict(params)
    _write(presets)


def delete_user_preset(name: str) -> bool:
    """Delete a user preset. Returns True when removed."""
    presets = load_user_presets()
    if name in presets:
        del presets[name]
        _write(presets)
        return True
    return False


def is_deletable(name) -> bool:
    """A preset is only deletable when it is a *user* one.

    The built-in presets ship with the app: removing them from the dropdown
    would have no lasting effect (``merge_presets`` would re-inject them on the
    next reload). A user preset masking a built-in one of the same name stays
    deletable — the built-in then reappears, which is the expected behaviour of
    :func:`merge_presets`.
    """
    return bool(name) and name in load_user_presets()


def merge_presets(builtins: dict) -> dict:
    """Merge built-in + user presets (the user one wins on a name collision).
    ``builtins`` is passed in by the caller (e.g. ``BRUSH_PRESETS``) so as not to
    invert the core→cli dependency."""
    merged = dict(builtins or {})
    merged.update(load_user_presets())
    return merged
