"""Synthetic multi-camera video generator for 4DGS e2e tests.

Produces several MP4 videos showing the same textured 3D corner scene from
different orbital viewpoints, using `_synthetic_scene.generate_scene` for the
frames and ffmpeg for encoding.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from tests.integration._synthetic_scene import generate_scene


def generate_multi_cam_videos(out_dir: Path, n_cams: int = 2, n_frames: int = 12,
                              w: int = 800, h: int = 600, fps: int = 5,
                              seed: int = 7) -> list[Path]:
    """Génère n_cams vidéos MP4 depuis des viewpoints orbitaux distincts.

    Utilise _synthetic_scene.generate_scene pour produire des PNG texturés
    (coin de boîte 3D), puis les encode en MP4 via ffmpeg.

    Returns: liste des chemins des vidéos générées.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"

    total_frames = n_frames * n_cams
    tmp_frames = Path(out_dir) / ".tmp_frames"
    generate_scene(tmp_frames, n_views=total_frames, w=w, h=h, seed=seed)

    video_paths: list[Path] = []
    for cam_idx in range(n_cams):
        start = cam_idx * n_frames
        video_path = out_dir / f"cam_{cam_idx:02d}.mp4"

        cmd = [
            ffmpeg_bin,
            "-framerate", str(fps),
            "-i", str(tmp_frames / "view_%03d.png"),
            "-start_number", str(start),
            "-vframes", str(n_frames),
            "-pix_fmt", "yuv420p",
            "-y",
            str(video_path),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed for cam_{cam_idx:02d}: {result.stderr}"
            )
        if not video_path.exists():
            raise RuntimeError(f"video not created: {video_path}")

        video_paths.append(video_path)

    shutil.rmtree(tmp_frames, ignore_errors=True)
    return video_paths
