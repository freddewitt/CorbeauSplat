"""Synthetic 2D image generators for Sharp and Upscale e2e tests.

numpy + PIL only — no cv2/opencv dependency.
"""
from __future__ import annotations

import shutil
import subprocess
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


def generate_equirectangular_image(out_path: Path, w: int = 1024, h: int = 512, seed: int = 13) -> Path:
    """Equirectangular (360°) panorama image with 2:1 aspect ratio.

    Generates a synthetic panorama with horizontal bands, multi-octave texture,
    and geometric markers at different longitudes. The 2:1 aspect ratio is
    standard for 360° panoramic images.

    For 360 Extractor: rich enough content for frame extraction at multiple
    viewpoints. Deterministic via np.random.default_rng(seed).

    Returns the Path to the generated PNG.
    """
    rng = np.random.default_rng(seed)
    img = np.zeros((h, w, 3), dtype=np.float32)

    # ── Latitude-based (vertical) gradient: sky-to-ground ────────────────────
    y_norm = np.linspace(0, 1, h)[:, None]
    # Sky: light blue at top
    img[..., 0] = 135 + 120 * (1 - y_norm)  # R: sky blue to darker
    img[..., 1] = 206 + 49 * (1 - y_norm)   # G: sky blue to darker
    img[..., 2] = 235                       # B: relatively constant (sky)
    # Ground: earth tones at bottom
    ground_factor = np.where(y_norm > 0.6, (y_norm - 0.6) / 0.4, 0)
    img[..., 0] = np.where(y_norm > 0.6, 139 + 60 * ground_factor, img[..., 0])
    img[..., 1] = np.where(y_norm > 0.6, 106 + 40 * ground_factor, img[..., 1])
    img[..., 2] = np.where(y_norm > 0.6, 90, img[..., 2])

    # ── Multi-octave texture (longitude-aware for panoramic feel) ────────────
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
    img = 0.65 * img + 0.35 * texture
    img = np.clip(img, 0, 255)

    # ── Geometric markers at different longitudes ──────────────────────────
    Y, X = np.ogrid[:h, :w]

    # Marker 1: Circle at longitude 45° (west; x ≈ w/8)
    cx1, cy = w // 8, h // 3
    r = h // 12
    mask = (X - cx1) ** 2 + (Y - cy) ** 2 <= r ** 2
    img[mask] = rng.integers(200, 255, size=3).astype(np.float32)

    # Marker 2: Rectangle at longitude 135° (south; x ≈ 3w/8)
    x2_0, y2_0 = w * 3 // 8, h // 2
    x2_1, y2_1 = x2_0 + w // 12, y2_0 + h // 8
    img[y2_0:y2_1, x2_0:x2_1] = rng.integers(100, 180, size=3).astype(np.float32)

    # Marker 3: Circle at longitude 225° (east; x ≈ 5w/8)
    cx3, cy3 = w * 5 // 8, h * 2 // 3
    r = h // 14
    mask = (X - cx3) ** 2 + (Y - cy3) ** 2 <= r ** 2
    img[mask] = rng.integers(50, 150, size=3).astype(np.float32)

    # Marker 4: Small square at longitude 315° (north; x ≈ 7w/8)
    x4_0, y4_0 = w * 7 // 8, h // 4
    x4_size = w // 16
    img[y4_0:y4_0 + x4_size, x4_0:x4_0 + x4_size] = rng.integers(150, 200, size=3).astype(np.float32)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img.astype(np.uint8)).save(out_path)
    return out_path


def generate_synthetic_video(out_path: Path, duration: float = 2.0, fps: int = 2,
                            w: int = 320, h: int = 240) -> Path:
    """Generate a short synthetic video using ffmpeg color/noise filters.

    Creates an MP4 video with animated color gradient. Uses ffmpeg's lavfi
    (libavfilter) to generate frames on the fly without intermediate file
    storage. Fast and lightweight.

    Parameters
    ----------
    out_path : Path
        Output video file path (should end with .mp4)
    duration : float, default 2.0
        Video duration in seconds
    fps : int, default 2
        Frames per second (2 fps × 2 sec = ~4 frames)
    w, h : int
        Video resolution (320×240 by default for speed)

    Returns
    -------
    Path
        Path to the generated video file
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"

    # Create an animated color pattern using ffmpeg filters
    # color: generates solid color, hue filter animates the hue over time
    # format=rgb24: ensures output is RGB (compatible with Sharp)
    filter_str = (
        f"color=c=blue:s={w}x{h},"
        f"hue=h=360*t/{duration}:s=100,"
        "format=rgb24"
    )

    cmd = [
        ffmpeg_bin,
        "-f", "lavfi",
        "-i", filter_str,
        "-t", str(duration),
        "-r", str(fps),
        "-pix_fmt", "yuv420p",
        "-y",
        str(out_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed: {result.stderr}"
            )
    except subprocess.TimeoutExpired:
        if out_path.exists():
            out_path.unlink()
        raise RuntimeError("ffmpeg timeout generating video")

    if not out_path.exists():
        raise RuntimeError(f"Video file not created: {out_path}")

    return out_path
