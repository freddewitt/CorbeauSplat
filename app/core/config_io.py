"""Saving/loading *named, reusable* configurations of the whole chain
(Load/Save icons of the top bar).

Distinct from ``SessionManager`` (which persists the single current GUI session
in ``config.json``): here several named, reusable configurations live, each in
its own file under ``configs/``.

Per-section serialisation reuses the ``to_dict``/``from_dict`` contract already
in place (``ColmapParams``, ``BrushParams``, ``RunState``) rather than
duplicating a parallel logic. Since ``from_dict`` tolerates missing/unknown
keys, a config saved by an earlier version reloads without breaking.
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
    """Folder of the named configurations (created on demand)."""
    d = resolve_project_root() / "configs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def is_safe_config_name(name: str) -> bool:
    """Same rule as the project name sanitisation (``engine.py``): no ``..``,
    ``/`` or ``\\``, and not empty.
    """
    if not name or not name.strip():
        return False
    return ".." not in name and "/" not in name and "\\" not in name


@dataclass
class ChainConfig:
    """Full chain configuration, serialisable to a named file."""

    version: int = CONFIG_VERSION
    source: dict = field(default_factory=dict)     # input_path, output_path, project_name, fps…
    extraction360: dict = field(default_factory=dict)  # sampling, layout, quality, AI
    upscale: dict = field(default_factory=dict)    # model, scale, format, tiles, TTA, compression
    colmap: dict = field(default_factory=dict)     # ColmapParams.to_dict()
    brush: dict = field(default_factory=dict)      # BrushParams.to_dict()
    cleaning: dict = field(default_factory=dict)   # strength, opacity_min, scale_pct, outlier_pct
    export: dict = field(default_factory=dict)     # target format, scale…
    flags: dict = field(default_factory=dict)      # RunState.to_dict()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ChainConfig":
        """Rebuild a config from a dict, tolerant of missing sections and of
        earlier versions.
        """
        if not isinstance(data, dict):
            return cls()
        data = _migrate(dict(data))
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    # Typed helpers: reload objects from the sections, leaning on the
    # tolerance of their respective from_dict.
    def colmap_params(self) -> ColmapParams:
        return ColmapParams.from_dict(self.colmap or {})

    def run_state(self) -> RunState:
        return RunState.from_dict(self.flags or {})


def _migrate(data: dict) -> dict:
    """Extension point for future schema migrations. Identity for now
    (version 1). Unknown versions are loaded on a best-effort basis.
    """
    return data


def save_config(name: str, config: ChainConfig | dict) -> "object":
    """Write a named configuration. Returns the file path."""
    if not is_safe_config_name(name):
        raise ValueError(f"Nom de configuration invalide: {name!r}")
    data = config.to_dict() if isinstance(config, ChainConfig) else dict(config)
    data.setdefault("version", CONFIG_VERSION)
    path = configs_dir() / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def load_config(name: str) -> ChainConfig:
    """Load a named configuration. Raises ``FileNotFoundError`` when missing."""
    if not is_safe_config_name(name):
        raise ValueError(f"Nom de configuration invalide: {name!r}")
    path = configs_dir() / f"{name}.json"
    with open(path, encoding="utf-8") as f:
        return ChainConfig.from_dict(json.load(f))


def list_configs() -> list:
    """Names of the available configurations (sorted)."""
    try:
        return sorted(p.stem for p in configs_dir().glob("*.json"))
    except OSError as e:
        logger.warning("Impossible de lister les configurations: %s", e)
        return []


def delete_config(name: str) -> bool:
    """Delete a named configuration. Returns True when a file was removed."""
    if not is_safe_config_name(name):
        raise ValueError(f"Nom de configuration invalide: {name!r}")
    path = configs_dir() / f"{name}.json"
    if path.exists():
        path.unlink()
        return True
    return False
