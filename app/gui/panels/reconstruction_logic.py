"""Logique (hors Qt) du panneau Reconstruction — testable sous mock PySide6.

Classe le dossier passé au sélecteur « Reprise de COLMAP » en deux cas gérés par
le même champ (spec §3 Reconstruction) :
- **projet CorbeauSplat existant** → reprise classique (réutilise ``images/``,
  écrase ``sparse/`` + ``database.db``) ;
- **dossier externe d'images** → nouveau projet créé à la volée.
"""

from pathlib import Path
from typing import Literal

from app.core.params import blur_factor_from_strength

# Mêmes extensions que ColmapEngine (app/core/engine.py).
_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
# Mêmes extensions vidéo que ColmapEngine._collect_video_paths (app/core/engine.py)
# et studio_window._VIDEO_EXTS (app/gui/studio_window.py) — les trois call sites
# doivent s'accorder sur ce qui compte comme une vidéo.
_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv"}

RESUME_COLMAP_PROJECT = "colmap_project"
RESUME_EXTERNAL_IMAGES = "external_images"
RESUME_INVALID = "invalid"


def classify_resume_folder(path):
    """Retourne l'une des constantes ``RESUME_*`` selon le contenu du dossier.

    - projet COLMAP : présence de ``images/``, ``database.db`` ou ``sparse/`` ;
    - dossier externe : au moins un fichier image directement dedans ;
    - invalide sinon (dossier absent, vide, ou non-dossier).
    """
    try:
        p = Path(path)
        if not p.is_dir():
            return RESUME_INVALID
    except (TypeError, ValueError, OSError):
        return RESUME_INVALID

    if (p / "images").is_dir() or (p / "database.db").exists() or (p / "sparse").is_dir():
        return RESUME_COLMAP_PROJECT

    try:
        for child in p.iterdir():
            if child.is_file() and child.suffix.lower() in _IMAGE_EXTS:
                return RESUME_EXTERNAL_IMAGES
    except OSError:
        return RESUME_INVALID

    return RESUME_INVALID


def detect_source_kind(path) -> Literal["images", "video", "mixed", "empty"]:
    """Classify a Source path as ``"images"``/``"video"``/``"mixed"``/``"empty"``.

    Pure function, no Qt dependency — used by ``SourcePanel`` for the live FPS
    field / mixed-content banner, and meant to replace ``studio_window.
    _detect_input_type`` (authoritative check at launch time) in a later pass.
    Unlike that older helper, this one distinguishes ``"mixed"`` (both images
    and videos found in the same folder) from a clean ``"images"``/``"video"``
    match.

    A single file is classified directly from its extension. A directory is
    scanned one level deep (no recursion, matching ``_detect_input_type``'s
    behaviour) and classified from the extensions found inside. Never raises:
    a missing/unreadable path or an unsupported extension resolves to
    ``"empty"``.
    """
    if not path:
        return "empty"
    try:
        p = Path(path)
    except (TypeError, ValueError):
        return "empty"

    try:
        if p.is_file():
            suffix = p.suffix.lower()
            if suffix in _VIDEO_EXTS:
                return "video"
            if suffix in _IMAGE_EXTS:
                return "images"
            return "empty"

        if not p.is_dir():
            return "empty"

        has_image = False
        has_video = False
        for child in p.iterdir():
            if not child.is_file():
                continue
            suffix = child.suffix.lower()
            if suffix in _IMAGE_EXTS:
                has_image = True
            elif suffix in _VIDEO_EXTS:
                has_video = True
    except OSError:
        return "empty"

    if has_image and has_video:
        return "mixed"
    if has_video:
        return "video"
    if has_image:
        return "images"
    return "empty"


def apply_source_blur_settings(params, source_state):
    """Report the blur filter settings from Source onto a ``ColmapParams``.

    The checkbox and the strength combo live in ``SourcePanel`` while the rest of
    the COLMAP settings live in ``ReconstructionPanel``; without this bridge the
    two fields never reach the engine (``ColmapEngine._process_input`` requires
    ``filter_blurry``). Mirrors what the CLI does in ``app/cli/commands.py``.

    Returns *params* so callers can chain.
    """
    params.filter_blurry = bool(source_state.get("filter_blur", False))
    params.blur_factor = blur_factor_from_strength(source_state.get("blur_strength") or "medium")
    return params
