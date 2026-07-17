#!/usr/bin/env python3
"""CorbeauSplat CLI package — command-line interface and GUI launcher."""
import sys

from app.core.system import check_dependencies

from .commands import (
    BRUSH_DEFAULTS,
    BRUSH_PRESETS,
    DISPATCH,
    run_4dgs,
    run_brush,
    run_clean,
    run_colmap,
    run_extract360,
    run_pipeline,
    run_sharp,
    run_supersplat,
    run_upscale,
)
from .launcher import _launch_gui
from .parser import get_parser

__all__ = [
    "BRUSH_DEFAULTS",
    "BRUSH_PRESETS",
    "DISPATCH",
    "main",
    "run_4dgs",
    "run_brush",
    "run_clean",
    "run_colmap",
    "run_extract360",
    "run_pipeline",
    "run_sharp",
    "run_supersplat",
    "run_upscale",
]


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
