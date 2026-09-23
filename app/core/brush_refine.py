"""Pure (Qt-free) helpers for Brush's Refine (resume-training) mode.

Extracted from ``app.gui.workers.BrushWorker._prepare_refine_environment`` so
the CLI (``brush``/``pipeline`` with ``--refine_mode``) can reproduce the
exact same "resume from the latest checkpoint" semantics as the GUI instead
of storing the flag and never acting on it (audit L4-04).
"""
from __future__ import annotations

import os
import re
import shutil
from collections.abc import Callable
from pathlib import Path


class RefineEnvironmentError(Exception):
    """Raised when the ``Refine`` working folder cannot be prepared.

    The message states which step failed (folder creation, init.ply copy, or
    sparse/images linking), matching the wording the GUI used to emit on
    ``finished_signal`` before this logic was extracted.
    """


def find_latest_checkpoint(
    checkpoints_dir: Path,
    log: Callable[[str], None] = lambda _msg: None,
) -> Path | None:
    """Return the most recently written ``.ply`` under ``checkpoints_dir``, or None."""
    latest_ply = None
    last_mtime = 0.0
    if checkpoints_dir.exists():
        log(f"Recherche de checkpoints dans {checkpoints_dir}...")
        for ply_path in checkpoints_dir.rglob("*.ply"):
            mt = ply_path.stat().st_mtime
            if mt > last_mtime:
                last_mtime = mt
                latest_ply = ply_path
    return latest_ply


def prepare_refine_environment(
    resolved_input: Path,
    log: Callable[[str], None] = lambda _msg: None,
) -> tuple[Path, Path] | Path:
    """Build the ``Refine`` folder and redirect training into it.

    Locates the most recently modified checkpoint under
    ``resolved_input/checkpoints``, copies it to ``Refine/init.ply``, and
    symlinks (falling back to copying) ``sparse``/``images`` next to it.

    Parameters
    ----------
    resolved_input: Path
        Dataset root (already resolved to the ``sparse``/``images`` parent).
    log: Callable[[str], None]
        Sink for progress/diagnostic messages (``print`` for the CLI,
        ``log_signal.emit`` for the GUI worker).

    Returns
    -------
    ``(refine_dir, latest_checkpoint)`` when a checkpoint was found and the
    Refine folder was built successfully. ``resolved_input`` unchanged when
    no checkpoint exists under ``checkpoints/`` — refine mode is then a
    no-op and the caller should train normally.

    Raises
    ------
    RefineEnvironmentError
        When the Refine folder cannot be prepared; the failure has already
        been reported via ``log`` before this is raised.
    """
    log("Mode Raffinement (Refine) activé...")
    latest_ply = find_latest_checkpoint(resolved_input / "checkpoints", log=log)

    if not latest_ply:
        log(
            "AVERTISSEMENT: Mode Refine activé mais aucun checkpoint (.ply) trouvé. "
            "Lancement mode normal."
        )
        return resolved_input

    log(f"Checkpoint trouvé: {latest_ply.name}")

    refine_dir = resolved_input / "Refine"
    log(f"Préparation du dossier de raffinement: {refine_dir}")
    try:
        if refine_dir.exists():
            shutil.rmtree(refine_dir)
        refine_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        log(f"ERREUR lors de la préparation du dossier Refine: {e}")
        raise RefineEnvironmentError(f"Erreur dossier Refine: {e}") from e

    dest_init = refine_dir / "init.ply"
    try:
        shutil.copy2(latest_ply, dest_init)
        log(f"Copié {latest_ply.name} vers {dest_init}")
    except Exception as e:
        log(f"ERREUR lors de la copie de init.ply: {e}")
        raise RefineEnvironmentError(f"Erreur copie init.ply: {e}") from e

    try:
        log("Création des liens symboliques pour sparse et images...")
        for name in ("sparse", "images"):
            try:
                os.symlink(resolved_input / name, refine_dir / name)
            except OSError as e:
                log(f"Symlink {name} échoué ({e}), tentative copie (plus lent)...")
                shutil.copytree(resolved_input / name, refine_dir / name)
        log("Liens symboliques/copies terminés.")
    except Exception as e:
        log(f"Erreur fatale lors de la création de l'environnement Refine: {e}")
        raise RefineEnvironmentError(f"Erreur env Refine: {e}") from e

    return refine_dir, latest_ply


def detect_refine_start_iteration(latest_ply: Path, total_steps: int = 30000) -> int:
    """Iteration number encoded in a checkpoint's filename, or ``total_steps`` as fallback."""
    match = re.search(r"iteration_(\d+)", latest_ply.name)
    if match:
        return int(match.group(1))
    return total_steps
