"""F-013 — Pillow's decompression-bomb guard must stay armed.

The app used to disable the guard globally (``PIL.Image.MAX_IMAGE_PIXELS = None``)
so large drone/upscale intermediates would not be refused. That left every
app-wide PIL decode unbounded: a forged image declaring huge dimensions while
holding a few dozen bytes on disk would trigger a giant allocation at
``Image.open``/``convert``/``resize``. The guard is now armed again with a
generous ceiling: forged bombs are refused at open (before any full decode),
legitimate images still convert.
"""
import io
import struct
import zlib
from pathlib import Path

import pytest

import app  # noqa: F401 — importing the package is what arms the guard

GUARD_FLOOR = 100_000_000
GUARD_CEILING = 10_000_000_000


def test_guard_is_armed_with_a_finite_ceiling():
    """Importing ``app`` must leave Pillow's guard armed and finite.

    Fails before the fix: ``app/__init__.py`` set ``MAX_IMAGE_PIXELS = None``,
    which disables the check altogether.
    """
    from PIL import Image

    assert Image.MAX_IMAGE_PIXELS is not None
    assert GUARD_FLOOR <= Image.MAX_IMAGE_PIXELS <= GUARD_CEILING


def _forged_png(path: Path, width: int, height: int) -> Path:
    """A tiny PNG whose IHDR claims ``width`` x ``height`` pixels.

    Width/height live at byte offsets 16-23 (after the 8-byte signature, the
    chunk length and the chunk type); the IHDR CRC is recomputed so Pillow
    trusts the header at ``Image.open``. The IDAT still holds a single 1x1
    scanline, so a full decode is impossible — which is exactly why the guard
    must refuse at open rather than attempt the allocation.
    """
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (1, 1), (0, 0, 0)).save(buf, "PNG")
    data = bytearray(buf.getvalue())
    struct.pack_into(">II", data, 16, width, height)
    crc = zlib.crc32(bytes(data[12:16 + 13])) & 0xFFFFFFFF
    struct.pack_into(">I", data, 16 + 13, crc)
    path.write_bytes(data)
    return path


def test_forged_bomb_is_refused_at_open(tmp_path):
    """A file declaring pathological dimensions raises before any decode.

    Fails before the fix: with the guard disabled the same file opens cleanly
    and reports the forged size (200000 x 200000), the first step towards a
    giant allocation.
    """
    from PIL import Image

    bomb = _forged_png(tmp_path / "bomb.png", width=200_000, height=200_000)

    with pytest.raises(Image.DecompressionBombError):
        Image.open(bomb)


def test_legitimate_image_still_converts(tmp_path):
    """The bound must not break ordinary images (over-correction guard)."""
    from PIL import Image

    from app.core.media import convert_image

    src = _forged_png(tmp_path / "seed.png", 1, 1)
    dest = tmp_path / "out.png"

    assert convert_image(src, dest, "png")
    with Image.open(dest) as out:
        assert out.size == (1, 1)
