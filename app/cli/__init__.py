#!/usr/bin/env python3
"""CorbeauSplat CLI package — command-line interface and GUI launcher."""
import sys

from .parser import get_parser
from .commands import (
    run_colmap,
    run_brush,
    run_supersplat,
    run_upscale,
    run_4dgs,
    run_extract360,
    run_pipeline,
    DISPATCH,
    BRUSH_DEFAULTS,
    BRUSH_PRESETS,
)
from .launcher import _launch_gui
from app.core.system import check_dependencies


def main():
    parser = get_parser()
    args = parser.parse_args()

    # No subcommand + no --gui → GUI par défaut
    if not args.command and not args.gui:
        _launch_gui()
        return

    if args.gui:
        _launch_gui()
        return

    missing_deps = check_dependencies()
    if missing_deps:
        print(f"Attention : dépendances manquantes : {', '.join(missing_deps)}")

    handler = DISPATCH.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(0)
