"""Générateur de scène 3D synthétique pour les tests end-to-end réels.

Produit un jeu d'images multi-vues qu'un vrai COLMAP peut reconstruire, sans
aucune donnée binaire versionnée ni dépendance réseau. La scène est un « coin »
de boîte (3 quads perpendiculaires) recouvert d'une texture multi-échelle riche.

Choix techniques (validés contre COLMAP 4.1) :
- **3 faces non coplanaires** → géométrie 3D non dégénérée (évite l'ambiguïté
  planaire fatale à l'estimation de pose en SfM).
- **Bruit multi-octave** (grilles aléatoires ré-échantillonnées à plusieurs
  échelles) → coins/blobs cohérents et stables d'une vue à l'autre, contrairement
  au bruit par-pixel qui donne peu de features et beaucoup de faux appariements.
- **numpy + PIL uniquement** (pas de cv2) → fonctionne dans le venv de test, où
  OpenCV n'est pas installé.
- **Sortie PNG** → pas d'artefacts JPEG qui déstabilisent les descripteurs SIFT.

Rendu par projection sténopé + échantillonnage inverse par homographie
(algorithme du peintre pour l'occlusion).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def _make_texture(seed: int, size: int = 512) -> np.ndarray:
    """Texture RGB à bruit multi-octave, contraste étiré sur toute la plage."""
    rng = np.random.default_rng(seed)
    acc = np.zeros((size, size, 3), np.float32)
    weight = 0.0
    for cells, amp in [(8, 1.0), (16, 0.7), (32, 0.5), (64, 0.35), (128, 0.2)]:
        grid = rng.integers(0, 256, (cells, cells, 3)).astype(np.uint8)
        up = np.array(Image.fromarray(grid).resize((size, size), Image.BICUBIC), np.float32)
        acc += amp * up
        weight += amp
    tex = acc / weight
    tex = (tex - tex.min()) / max(float(np.ptp(tex)), 1e-6) * 255.0
    return np.clip(tex, 0, 255).astype(np.uint8)


def _look_at(eye: np.ndarray, target: np.ndarray,
             up: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Rotation/translation monde→caméra (convention OpenCV : +Z avant, +Y bas)."""
    if up is None:
        up = np.array([0.0, 0.0, 1.0])
    fwd = target - eye
    fwd = fwd / np.linalg.norm(fwd)
    right = np.cross(fwd, up)
    right = right / np.linalg.norm(right)
    down = np.cross(fwd, right)
    R = np.stack([right, down, fwd], axis=0)
    return R, -R @ eye


def _project(pts_w: np.ndarray, R: np.ndarray, t: np.ndarray,
             K: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    pc = (R @ pts_w.T).T + t
    proj = (K @ pc.T).T
    return proj[:, :2] / proj[:, 2:3], pc[:, 2]


def _homography(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """Homographie DLT envoyant src[i] → dst[i] (4 correspondances)."""
    A = []
    for (x, y), (u, v) in zip(src, dst, strict=False):
        A.append([-x, -y, -1, 0, 0, 0, u * x, u * y, u])
        A.append([0, 0, 0, -x, -y, -1, v * x, v * y, v])
    _, _, Vt = np.linalg.svd(np.array(A, float))
    return (Vt[-1] / Vt[-1, -1]).reshape(3, 3)


def _draw_face(img: np.ndarray, dst_uv: np.ndarray, tex: np.ndarray) -> None:
    """Plaque une texture sur un quad projeté (échantillonnage inverse)."""
    ts = tex.shape[0]
    tex_corners = np.array([[0, 0], [ts - 1, 0], [ts - 1, ts - 1], [0, ts - 1]], float)
    h, w = img.shape[:2]
    x0, y0 = np.floor(dst_uv.min(0)).astype(int)
    x1, y1 = np.ceil(dst_uv.max(0)).astype(int)
    x0, y0 = max(x0, 0), max(y0, 0)
    x1, y1 = min(x1, w - 1), min(y1, h - 1)
    if x1 <= x0 or y1 <= y0:
        return
    try:
        h_inv = _homography(dst_uv, tex_corners)  # px destination → uv texture
    except np.linalg.LinAlgError:
        return
    ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
    dest = np.stack([xs.ravel(), ys.ravel(), np.ones(xs.size)], 0)
    src = h_inv @ dest
    u = src[0] / src[2]
    v = src[1] / src[2]
    valid = (u >= 0) & (u < ts) & (v >= 0) & (v < ts)
    ui = np.clip(u.astype(int), 0, ts - 1)
    vi = np.clip(v.astype(int), 0, ts - 1)
    patch = img[y0:y1 + 1, x0:x1 + 1].reshape(-1, 3)
    sampled = tex[vi, ui]
    patch[valid] = sampled[valid]
    img[y0:y1 + 1, x0:x1 + 1] = patch.reshape(y1 - y0 + 1, x1 - x0 + 1, 3)


def generate_scene(out_dir: Path, n_views: int = 24, w: int = 800, h: int = 600,
                   seed: int = 7) -> int:
    """Génère ``n_views`` images PNG d'un coin de boîte texturé dans ``out_dir``.

    Retourne le nombre d'images écrites. Déterministe pour un ``seed`` donné.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    faces = [
        (np.array([[0, 0, 2], [2, 0, 2], [2, 0, 0], [0, 0, 0]], float), 1),  # mur Y=0
        (np.array([[0, 0, 2], [0, 2, 2], [0, 2, 0], [0, 0, 0]], float), 2),  # mur X=0
        (np.array([[0, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0]], float), 3),  # sol Z=0
    ]
    textures = {s: _make_texture(s * 101 + seed) for _, s in faces}
    focal = 0.9 * w
    K = np.array([[focal, 0, w / 2], [0, focal, h / 2], [0, 0, 1]], float)
    target = np.array([1.0, 1.0, 1.0])
    radius = 4.5
    for i in range(n_views):
        ang = np.deg2rad(20 + 50 * i / max(1, n_views - 1))
        elev = np.deg2rad(25 + 10 * np.sin(i * 0.7))
        eye = target + radius * np.array([
            np.cos(ang) * np.cos(elev),
            np.sin(ang) * np.cos(elev),
            np.sin(elev) + 0.4,
        ])
        R, t = _look_at(eye, target)
        img = np.zeros((h, w, 3), np.uint8)
        faces_by_depth = sorted(
            ((_project(quad, R, t, K), s) for quad, s in faces),
            key=lambda e: -e[0][1].mean(),   # face la plus lointaine d'abord
        )
        for (uv, _z), s in faces_by_depth:
            _draw_face(img, uv, textures[s])
        Image.fromarray(img).save(out_dir / f"view_{i:03d}.png")
    return n_views
