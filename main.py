#!/usr/bin/env python3
"""CorbeauSplat — Gaussian Splatting toolkit with GUI."""

import os
import sys

# Ensure the app package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.cli import main

if __name__ == "__main__":
    main()
