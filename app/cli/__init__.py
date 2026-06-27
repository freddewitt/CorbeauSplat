#!/usr/bin/env python3
"""CorbeauSplat CLI package — command-line interface and GUI launcher."""
import sys

from app.core.system import check_dependencies

from .launcher import _launch_gui
from .parser import get_parser


def main():
    parser = get_parser()
    args = parser.parse_args()

    # No subcommand + no --gui → GUI par défaut.
    # The GUI is the default path, so the heavy CLI engine stack (.commands pulls
    # in ColmapEngine/BrushEngine/… and app.core.engine) is imported lazily in the
    # CLI branch below — a GUI launch must not pay for importing it.
    if not args.command and not args.gui:
        _launch_gui()
        return

    if args.gui:
        _launch_gui()
        return

    from .commands import DISPATCH

    missing_deps = check_dependencies()
    if missing_deps:
        print(f"Attention : dépendances manquantes : {', '.join(missing_deps)}")

    handler = DISPATCH.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(0)
