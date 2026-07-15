"""Synthetic 2D image generators for Sharp and Upscale e2e tests.

numpy + PIL only — no cv2/opencv dependency.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def generate_upscale_target(out_path: Path, w: int = 160, h: int = 120, seed: int = 11) -> Path:
    """Small image with high-frequency pattern (lines + structured noise).

    Small size = fast upscale. The pattern allows verifying that output is
    actually 4× larger (640×480) and not a raw copy.
    """
    rng = np.random.default_rng(seed)
    img = np.zeros((h, w, 3), dtype=np.uint8)

    # ── Colored checkerboard ────────────────────────────────────────────────
    n_x, n_y = 8, 6
    cell_w = w // n_x
    cell_h = h // n_y
    colors = rng.integers(40, 220, size=(n_x * n_y, 3), dtype=np.uint8)
    for iy in range(n_y):
        for ix in range(n_x):
            x0 = ix * cell_w
            y0 = iy * cell_h
            img[y0 : y0 + cell_h, x0 : x0 + cell_w] = colors[iy * n_x + ix]

    # ── Diagonal lines ──────────────────────────────────────────────────────
    for channel, offset_step in enumerate((12, 18, 24)):
        for offset in range(-h, w, offset_step):
            ys = np.arange(h)
            xs = ys + offset
            valid = (xs >= 0) & (xs < w)
            img[ys[valid], xs[valid], channel] = (
                img[ys[valid], xs[valid], channel].astype(np.int16) + 80
            ) % 256

    # ── High-frequency noise ────────────────────────────────────────────────
    noise = rng.integers(0, 40, size=(h, w, 3), dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img).save(out_path)
    return out_path


def generate_depth_image(out_path: Path, w: int = 640, h: int = 480, seed: int = 7) -> Path:
    """RGB image with spatial gradient + multi-octave textures.

    For Sharp: rich enough content for non-trivial depth estimation
    (textured zones at multiple scales, like _make_texture but in 2D).
    Deterministic via np.random.default_rng(seed).

    Returns the Path to the generated PNG.
    """
    rng = np.random.default_rng(seed)
    img = np.zeros((h, w, 3), dtype=np.float32)

    # ── Gradient background (light top → dark bottom) ───────────────────────
    y_norm = np.linspace(0, 1, h)[:, None]
    img[..., 0] = 255 * (1 - y_norm)
    img[..., 1] = 220 * (1 - y_norm)
    img[..., 2] = 180 * (1 - y_norm)

    # ── Multi-octave texture (same pattern as _synthetic_scene._make_texture) ─
    texture = np.zeros((h, w, 3), dtype=np.float32)
    weight = 0.0
    for cells, amp in [(8, 1.0), (16, 0.7), (32, 0.5), (64, 0.35), (128, 0.2)]:
        grid = rng.integers(0, 256, (cells, cells, 3), dtype=np.uint8)
        up = np.array(Image.fromarray(grid).resize((w, h), Image.BICUBIC), dtype=np.float32)
        texture += amp * up
        weight += amp
    texture = texture / weight
    texture = (texture - texture.min()) / max(float(np.ptp(texture)), 1e-6) * 255.0
    texture = np.clip(texture, 0, 255)

    # Blend gradient and texture
    img = 0.6 * img + 0.4 * texture
    img = np.clip(img, 0, 255)

    # ── Geometric shapes at different positions ─────────────────────────────
    Y, X = np.ogrid[:h, :w]

    # Circle near top-left
    cx, cy = w // 4, h // 3
    r = h // 10
    mask = (X - cx) ** 2 + (Y - cy) ** 2 <= r ** 2
    img[mask] = rng.integers(40, 220, size=3).astype(np.float32)

    # Rectangle in the middle
    x0, y0 = w // 2, h // 3
    x1, y1 = x0 + w // 5, y0 + h // 6
    img[y0:y1, x0:x1] = rng.integers(40, 220, size=3).astype(np.float32)

    # Circle near bottom-right
    cx, cy = w * 3 // 4, h * 2 // 3
    r = h // 12
    mask = (X - cx) ** 2 + (Y - cy) ** 2 <= r ** 2
    img[mask] = rng.integers(40, 220, size=3).astype(np.float32)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img.astype(np.uint8)).save(out_path)
    return out_path
