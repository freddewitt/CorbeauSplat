"""Propagation des champs du panneau Projet vers les étapes chaînées.

Logique pure, sans Qt — même parti pris que ``reconstruction_logic.py`` : ces
règles décident où Brush écrit et où l'Export atterrit, elles méritent d'être
testables sans instancier ``StudioWindow`` (dont la classe de base Qt est un
MagicMock sous le harnais de test).
"""

from pathlib import Path

from app.core.base_engine import validate_path_standalone


def resolve_checkpoints_dir(source_state) -> Path | None:
    """Dossier où Brush écrit ses checkpoints — et où les étapes suivantes vont
    chercher le PLY produit.

    Par défaut ``<sortie>/<projet>/checkpoints``. Si le champ « Destination des
    checkpoints » du panneau Projet est renseigné, on reprend la sémantique
    d'origine du champ (CHANGELOG 1.2.3) à l'identique : ``<destination>/<projet>``,
    sans sous-dossier ``checkpoints``.

    Renvoie None si la sortie de base manque, ou si la destination saisie — une
    entrée utilisateur libre — ne se résout pas.
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
    """Une destination personnalisée ne conserve que le dernier checkpoint ;
    champ vide = comportement historique, tous les checkpoints gardés
    (CHANGELOG 1.2.3)."""
    return bool((source_state.get("checkpoint_dest") or "").strip())


def resolve_export_dir(source_state, ply_path, current_output) -> str | None:
    """Dossier de sortie de l'étape Export, ou None pour ne rien changer.

    Le champ « Dossier d'export » du panneau Projet, quand il est renseigné,
    l'emporte sur ce qui est saisi dans le panneau Export : c'est le réglage de
    la *chaîne*, alors que le panneau Export sert aussi au lancement local.
    Laissé vide, on retombe sur le comportement précédent — dossier du PLY
    source, et seulement si l'utilisateur n'a rien saisi lui-même.
    """
    export_dir = (source_state.get("export_dir") or "").strip()
    if export_dir:
        safe_dir = validate_path_standalone(export_dir)
        return str(safe_dir) if safe_dir is not None else None
    if current_output.strip():
        return None
    return str(Path(ply_path).parent)


def resolve_export_format(source_state) -> str:
    """Format d'export imposé par le panneau Projet, ou chaîne vide si le
    panneau Export garde la main."""
    return (source_state.get("export_format") or "").strip()
