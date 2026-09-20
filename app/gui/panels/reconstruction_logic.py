"""Logic (Qt-free) for the Reconstruction panel — testable under a mocked PySide6.

Classifies the folder passed to the "Resume COLMAP" selector into two cases
handled by the same field (spec §3 Reconstruction):
- **existing CorbeauSplat project** → classic resume (reuses ``images/``,
  overwrites ``sparse/`` + ``database.db``);
- **external image folder** → new project created on the fly.
"""

from pathlib import Path
from typing import Literal

from app.core.media import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from app.core.params import blur_factor_from_strength

# Same shared lists as ColmapEngine (app/core/media.py): anything beyond
# JPEG/PNG is accepted here and converted on ingest.
_IMAGE_EXTS = IMAGE_EXTENSIONS
# Single shared list (app/core/media.py): the panel, ColmapEngine and
# FourDGSEngine must agree on what counts as a video.
_VIDEO_EXTS = VIDEO_EXTENSIONS

RESUME_COLMAP_PROJECT = "colmap_project"
RESUME_EXTERNAL_IMAGES = "external_images"
RESUME_INVALID = "invalid"


def classify_resume_folder(path):
    """Return one of the ``RESUME_*`` constants based on the folder's content.

    - COLMAP project: presence of ``images/``, ``database.db`` or ``sparse/``;
    - external folder: at least one image file directly inside;
    - invalid otherwise (missing folder, empty, or not a folder).
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


def apply_source_settings(params, source_state):
    """Carry the Source panel's ingest settings onto a ``ColmapParams``.

    Some COLMAP inputs are chosen in ``SourcePanel`` rather than
    ``ReconstructionPanel``, because they describe the source rather than the
    reconstruction: the blur filter and the image conversion format. Without
    this bridge they never reach the engine, which reads them from params
    (``ColmapEngine._process_input``). Mirrors what the CLI does in
    ``app/cli/commands.py``.

    Named for the settings, not just the blur one it originally carried.

    Returns *params* so callers can chain.
    """
    params.filter_blurry = bool(source_state.get("filter_blur", False))
    params.blur_factor = blur_factor_from_strength(source_state.get("blur_strength") or "medium")
    params.image_convert_format = source_state.get("convert") or "png"

    # In/out range picked in the Source panel. Absent or malformed means the
    # whole video, so a configuration saved before the feature existed, or one
    # whose video was swapped, simply extracts everything.
    trim = source_state.get("video_trim")
    if isinstance(trim, dict):
        params.video_trim_start = trim.get("start")
        params.video_trim_end = trim.get("end")
    else:
        params.video_trim_start = None
        params.video_trim_end = None
    return params


def describe_unusable_source(path, convert_format="png") -> str:
    """Explain why a source yielded no usable media, in the user's terms.

    `detect_source_kind` collapses every failure into "empty", and the launch
    path then reported "Chemins manquants" — actively misleading when the path
    is perfectly valid and simply holds a format the chain cannot read (camera
    RAW, PSD…). This says what was found, what is accepted, and — because the
    accepted list is wider than JPEG/PNG only thanks to on-ingest conversion —
    what the conversion setting is currently doing.
    """
    if not path or not str(path).strip():
        return "Aucun chemin source n'est renseigné."

    p = Path(str(path).strip())
    if not p.exists():
        return f"Chemin introuvable : {p}"

    accepted = ", ".join(sorted(e.lstrip(".") for e in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS))

    if p.is_file():
        found = p.suffix.lower().lstrip(".") or "sans extension"
        detail = f"Le fichier « {p.name} » est au format {found}, non pris en charge."
    else:
        suffixes = sorted({f.suffix.lower().lstrip(".") for f in p.iterdir()
                           if f.is_file() and f.suffix})
        if not suffixes:
            detail = f"Le dossier « {p.name} » ne contient aucun fichier exploitable."
        else:
            detail = (f"Le dossier « {p.name} » ne contient aucune image ni vidéo reconnue "
                      f"(formats trouvés : {', '.join(suffixes)}).")

    message = f"{detail}\n\nFormats acceptés : {accepted}."

    if convert_format == "off":
        message += (
            "\n\n⚠️ La conversion est désactivée (réglage « convert » = off). "
            "Les formats autres que JPEG et PNG ne sont alors pas convertis et "
            "seront refusés par la suite de la chaîne."
        )
    else:
        message += (
            f"\n\nLes formats hors JPEG/PNG sont convertis automatiquement en "
            f"{convert_format.upper()} à l'ingestion (réglage « convert » — "
            f"CLI : --convert png|jpeg|off). Les originaux ne sont pas modifiés."
        )
    return message
