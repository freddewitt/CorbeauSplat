"""Choosing the right COLMAP sub-model under ``sparse/``.

The incremental mapper writes one folder per reconstruction it manages to
grow (``sparse/0``, ``sparse/1``, ...), in the order it found them, not by
size. A first attempt that stalls after two images still gets ``0/``, and the
real model lands in ``1/``. Every consumer (undistorter, Brush config,
Nerfstudio) reads ``sparse/0`` only, so the largest model is moved there.
"""
from __future__ import annotations

import re
import struct
from collections.abc import Callable
from pathlib import Path


def count_registered_images(model_dir: Path) -> int:
    """Number of registered images in a COLMAP model folder (.bin or .txt)."""
    model_dir = Path(model_dir)
    images_bin = model_dir / "images.bin"
    if images_bin.is_file():
        with images_bin.open("rb") as fh:
            header = fh.read(8)
        return struct.unpack("<Q", header)[0] if len(header) == 8 else 0
    images_txt = model_dir / "images.txt"
    if images_txt.is_file():
        count = 0
        for line in images_txt.read_text(errors="ignore").splitlines():
            declared = re.match(r"#\s*Number of images:\s*(\d+)", line)
            if declared:
                return int(declared.group(1))
            # Pose line: IMAGE_ID QW QX QY QZ TX TY TZ CAMERA_ID NAME (10 fields);
            # the points line that follows has a multiple of 3 fields.
            tokens = line.split()
            if len(tokens) == 10 and tokens[0].isdigit():
                count += 1
        return count
    return 0


def promote_largest_model(sparse_dir: Path, log: Callable[[str], None] | None = None) -> Path | None:
    """Make ``sparse/0`` the sub-model with the most registered images.

    Returns the path of ``sparse/0`` (or None when no model exists). When the
    largest model already sits in ``0/`` nothing is touched; otherwise the two
    folders swap names so nothing is lost.
    """
    sparse_dir = Path(sparse_dir)
    if not sparse_dir.is_dir():
        return None
    models = [d for d in sparse_dir.iterdir() if d.is_dir() and d.name.isdigit()]
    if not models:
        return None
    counts = {d: count_registered_images(d) for d in models}
    # Ties favour the lowest index, i.e. COLMAP's own order.
    best = max(models, key=lambda d: (counts[d], -int(d.name)))
    zero = sparse_dir / "0"
    if best != zero:
        if zero.exists():
            swap = sparse_dir / "_swap"
            zero.rename(swap)
            best.rename(zero)
            swap.rename(sparse_dir / best.name)
        else:
            best.rename(zero)
        if log:
            log(f"COLMAP produced {len(models)} sub-models: {best.name}/ "
                f"({counts[best]} images) promoted to 0/ "
                f"(was {counts.get(zero, 0)} images).")
    return zero
