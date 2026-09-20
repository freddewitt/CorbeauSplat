"""Propagation of the Projet panel fields to the chained steps.

Pure logic, no Qt — same stance as ``reconstruction_logic.py``: these rules
decide where Brush writes and where the Export lands, so they deserve to be
testable without instantiating ``StudioWindow`` (whose Qt base class is a
MagicMock under the test harness).
"""

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
