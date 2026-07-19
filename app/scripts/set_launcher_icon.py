"""Applique l'icône CorbeauSplat au fichier lanceur ``.command`` dans le Finder.

Utilise ``NSWorkspace`` via ``pyobjc-framework-Cocoa`` (déjà une dépendance du
projet — même pattern que ``_set_macos_dock_icon`` dans ``app/cli/launcher.py``,
mais ciblant un fichier du Finder plutôt que l'icône du Dock de l'application).

L'icône Finder d'un fichier est stockée dans ses métadonnées (resource fork /
xattr), pas trackée par git : ce module doit donc s'exécuter à chaque lancement
de ``run.command`` pour fonctionner aussi après un nouveau ``git clone``.
Idempotent : si l'icône actuelle du fichier correspond déjà à l'icône cible,
aucune écriture n'est effectuée.
"""
from pathlib import Path


def set_launcher_icon(launcher_path: Path, icon_path: Path) -> bool:
    """Applique ``icon_path`` comme icône Finder de ``launcher_path``.

    Retourne True si l'icône est (déjà) correctement appliquée, False si
    pyobjc/NSWorkspace est indisponible, si un des fichiers est manquant, ou
    en cas d'échec (défensif : n'appelle jamais raise).
    """
    if not launcher_path.exists() or not icon_path.exists():
        return False
    try:
        from AppKit import NSWorkspace, NSImage
    except Exception:
        return False
    try:
        workspace = NSWorkspace.sharedWorkspace()
        new_image = NSImage.alloc().initWithContentsOfFile_(str(icon_path))
        if new_image is None:
            return False

        # Idempotence: NSWorkspace always returns *some* icon for a file
        # (the generic one if none is set). Comparing TIFF bytes lets us
        # skip the write entirely when the icon is already correct.
        current_image = workspace.iconForFile_(str(launcher_path))
        if current_image is not None:
            current_tiff = bytes(current_image.TIFFRepresentation())
            new_tiff = bytes(new_image.TIFFRepresentation())
            if current_tiff == new_tiff:
                return True

        return bool(workspace.setIcon_forFile_options_(new_image, str(launcher_path), 0))
    except Exception:
        return False


def main():
    root_dir = Path(__file__).resolve().parent.parent.parent
    launcher_path = root_dir / "CorbeauSplat.command"
    icon_path = root_dir / "assets" / "icon.icns"
    set_launcher_icon(launcher_path, icon_path)


if __name__ == "__main__":
    main()
