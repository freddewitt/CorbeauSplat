"""Propagation of the Projet panel fields to the chained steps.

Pure logic, no Qt — same stance as ``reconstruction_logic.py``: these rules
decide where Brush writes and where the Export lands, so they deserve to be
testable without instantiating ``StudioWindow`` (whose Qt base class is a
MagicMock under the test harness).
"""

import re
from pathlib import Path

from app.core.base_engine import validate_path_standalone


def resolve_checkpoints_dir(source_state) -> Path | None:
    """Folder where Brush writes its checkpoints — and where the next steps
    look for the produced PLY.

    ``<output>/<project>/checkpoints`` by default. When the "Checkpoint
    destination" field of the Projet panel is filled in, we keep the original
    semantics of the field (CHANGELOG 1.2.3) identical:
    ``<destination>/<project>``, with no ``checkpoints`` sub-folder.

    Returns None when the base output is missing, or when the entered
    destination — free user input — does not resolve.
    """
    output_path = source_state["output_path"].strip()
    if not output_path:
        return None
    project_name = source_state["project_name"].strip() or "Untitled"
    dest = (source_state.get("checkpoint_dest") or "").strip()
    if dest:
        safe_dest = validate_path_standalone(dest)
        return safe_dest / project_name if safe_dest is not None else None
    return Path(output_path) / project_name / "checkpoints"


def keeps_only_latest_checkpoint(source_state) -> bool:
    """A custom destination only keeps the last checkpoint; an empty field =
    historical behaviour, every checkpoint kept (CHANGELOG 1.2.3)."""
    return bool((source_state.get("checkpoint_dest") or "").strip())


def is_chain_owned(current_value, last_prefilled) -> bool:
    """True when a panel field may be overwritten by the chain's pre-fill.

    The chain pre-fills the Nettoyage/Export output fields from the previous
    step, but a value typed by the user must survive. A field is still the
    chain's own when it is empty or holds exactly what the chain wrote last
    time; otherwise the user changed it. Without this, the second project run
    in one session kept the first project's paths and overwrote its files.
    """
    current = (current_value or "").strip()
    return not current or current == (last_prefilled or "")


def resolve_export_dir(source_state, ply_path, current_output) -> str | None:
    """Output folder of the Export step, or None to change nothing.

    The "Export folder" field of the Projet panel, when filled in, wins over
    whatever is typed into the Export panel: it is the *chain* setting, whereas
    the Export panel also serves local runs. Left empty, we fall back on the
    previous behaviour — folder of the source PLY, and only when the user typed
    nothing themselves.
    """
    export_dir = (source_state.get("export_dir") or "").strip()
    if export_dir:
        safe_dir = validate_path_standalone(export_dir)
        return str(safe_dir) if safe_dir is not None else None
    if current_output.strip():
        return None
    return str(Path(ply_path).parent)


def resolve_export_format(source_state) -> str:
    """Export format imposed by the Projet panel, or an empty string when the
    Export panel keeps control."""
    return (source_state.get("export_format") or "").strip()


# Brush names its checkpoints from the `--export-name` default, `export_{iter}.ply`.
# Two older layouts are still recognised because earlier runs (and other trainers)
# produced them: `iteration_<n>.ply` at the root, and the nested
# `point_cloud/iteration_<n>/point_cloud.ply`. Any of these may carry a project
# prefix added afterwards by _rename_checkpoints_with_project_name().
_CHECKPOINT_FILE_RE = re.compile(r"^(?:.+_)?(?:export|iteration)_\d+\.ply$")
_CHECKPOINT_NESTED_DIR_RE = re.compile(r"^iteration_\d+$")
_CHECKPOINT_BACKUP_DIR_RE = re.compile(r"^checkpoints_backup_\d+$")


def is_checkpoint_ply(path: Path, root: Path) -> bool:
    """True when `path` is a training checkpoint produced under `root`.

    Anything else found in the output folder belongs to the user — a training
    run must never move, rename or delete it. This guards the case where the
    output folder is also a working folder holding the user's own .ply files.
    Files already archived under `checkpoints_backup_*` are excluded too, so a
    later run cannot re-archive or prune away an earlier backup.
    """
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False

    parts = rel.parts
    if any(_CHECKPOINT_BACKUP_DIR_RE.match(part) for part in parts[:-1]):
        return False

    if _CHECKPOINT_FILE_RE.match(path.name):
        return True

    return (
        len(parts) >= 3
        and parts[-3] == "point_cloud"
        and _CHECKPOINT_NESTED_DIR_RE.match(parts[-2]) is not None
        and path.name.endswith("point_cloud.ply")
    )


def find_checkpoint_plys(root: Path) -> list[Path]:
    """All checkpoint .ply files under `root`, sorted, user files left out."""
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.ply") if p.is_file() and is_checkpoint_ply(p, root))
