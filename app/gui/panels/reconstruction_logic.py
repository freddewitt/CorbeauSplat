"""Logique (hors Qt) du panneau Reconstruction — testable sous mock PySide6.

Classe le dossier passé au sélecteur « Reprise de COLMAP » en deux cas gérés par
le même champ (spec §3 Reconstruction) :
- **projet CorbeauSplat existant** → reprise classique (réutilise ``images/``,
  écrase ``sparse/`` + ``database.db``) ;
- **dossier externe d'images** → nouveau projet créé à la volée.
"""

from pathlib import Path

# Mêmes extensions que ColmapEngine (app/core/engine.py).
_IMAGE_EXTS = {".jpg", ".jpeg", ".png"}

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
