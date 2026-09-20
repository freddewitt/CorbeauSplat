"""Apply the CorbeauSplat icon to the ``.command`` launcher file in the Finder.

Uses ``NSWorkspace`` through ``pyobjc-framework-Cocoa`` (already a project
dependency — same pattern as ``_set_macos_dock_icon`` in ``app/cli/launcher.py``,
but targeting a Finder file rather than the application's Dock icon).

The Finder icon of a file is stored in its metadata (resource fork / xattr), not
tracked by git: this module must therefore run on every launch of
``run.command`` so it also works after a fresh ``git clone``. Idempotent: when
the file's current icon already matches the target icon, nothing is written.
"""
from pathlib import Path

# pyobjc may not be available on non-macOS or minimal installs
try:
    from AppKit import NSWorkspace, NSImage  # noqa: I001
except ImportError:
    NSWorkspace = NSImage = None  # type: ignore[assignment,misc]


def set_launcher_icon(launcher_path: Path, icon_path: Path) -> bool:
    """Apply ``icon_path`` as the Finder icon of ``launcher_path``.

    Returns True when the icon is (already) correctly applied, False when
    pyobjc/NSWorkspace is unavailable, when one of the files is missing, or on
    failure (defensive: never raises).
    """
    if not launcher_path.exists() or not icon_path.exists():
        return False
    if NSWorkspace is None or NSImage is None:
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
