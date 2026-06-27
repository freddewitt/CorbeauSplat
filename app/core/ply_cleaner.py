"""
ply_cleaner.py — Automatic cleanup of Gaussian-Splat .ply files.

Removes the common junk produced by photogrammetry-based splatting:
  - near-transparent splats (low opacity → noise),
  - oversized splats (giant gaussians, e.g. sky "shells"),
  - spatial outliers / floaters far from the main point cloud.

The geometry/colour of the kept splats is preserved exactly — we only drop
whole splats, never alter the survivors. The original file is never modified
in place; callers pass an explicit output path.

numpy is imported lazily inside the compute functions (not at module load): this
module is pulled in at GUI startup via cleaner_tab → resolve_params, which needs
no numpy, so we keep numpy's ~100ms cold import off the time-to-window path.
"""

# Severity presets → (opacity_min on activated alpha, scale percentile, outlier percentile)
# Higher percentile = keep more (gentler); lower = remove more (stronger).
PRESETS = {
    "light":  {"opacity_min": 0.05, "scale_pct": 99.9, "outlier_pct": 99.9},
    "medium": {"opacity_min": 0.10, "scale_pct": 99.5, "outlier_pct": 99.5},
    "strong": {"opacity_min": 0.20, "scale_pct": 99.0, "outlier_pct": 99.0},
}


def _sigmoid(x):
    import numpy as np
    return 1.0 / (1.0 + np.exp(-x))


def compute_keep_mask(x, y, z, opacity, s0, s1, s2,
                      opacity_min=0.10, scale_pct=99.5, outlier_pct=99.5):
    """Compute a boolean keep-mask for a set of Gaussian splats.

    Parameters are 1-D numpy arrays (one entry per splat). `opacity` is the raw
    logit (pre-sigmoid) and `s0..s2` are log-scales, matching the 3DGS/Brush PLY
    convention. Returns (keep_mask, stats_dict).
    """
    import numpy as np
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    z = np.asarray(z, dtype=np.float64)
    opacity = np.asarray(opacity, dtype=np.float64)
    n = len(x)

    # 1. Opacity — drop near-invisible splats (noise).
    alpha = _sigmoid(opacity)
    m_op = alpha >= opacity_min

    # 2. Scale — drop oversized gaussians (sky shells / big floaters).
    sizes = np.maximum.reduce([
        np.exp(np.asarray(s0, dtype=np.float64)),
        np.exp(np.asarray(s1, dtype=np.float64)),
        np.exp(np.asarray(s2, dtype=np.float64)),
    ])
    if scale_pct >= 100.0 or n == 0:
        m_sc = np.ones(n, dtype=bool)
    else:
        scale_thr = np.percentile(sizes, scale_pct)
        m_sc = sizes <= scale_thr

    # 3. Spatial outliers — drop splats far from the cloud's robust centre.
    if outlier_pct >= 100.0 or n == 0:
        m_out = np.ones(n, dtype=bool)
    else:
        cx, cy, cz = np.median(x), np.median(y), np.median(z)
        dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2)
        dist_thr = np.percentile(dist, outlier_pct)
        m_out = dist <= dist_thr

    keep = m_op & m_sc & m_out
    stats = {
        "total": int(n),
        "kept": int(keep.sum()),
        "removed": int(n - keep.sum()),
        "removed_opacity": int((~m_op).sum()),
        "removed_scale": int((~m_sc).sum()),
        "removed_outlier": int((~m_out).sum()),
    }
    return keep, stats


def resolve_params(strength="medium", overrides=None):
    """Returns the cleaning parameter dict for a preset name, applying overrides."""
    params = dict(PRESETS.get(strength, PRESETS["medium"]))
    if overrides:
        params.update({k: v for k, v in overrides.items() if v is not None})
    return params


def clean_ply(input_path, output_path, strength="medium", overrides=None, log=None):
    """Clean a Gaussian-splat PLY and write the result to output_path.

    Returns a stats dict. Raises ValueError if the file is not a Gaussian splat.
    """
    from plyfile import PlyData, PlyElement

    def _log(msg):
        if log:
            log(msg)

    params = resolve_params(strength, overrides)
    _log(f"Lecture de {input_path} ...")
    ply = PlyData.read(str(input_path))

    if "vertex" not in ply:
        raise ValueError("PLY invalide : élément 'vertex' absent.")
    data = ply["vertex"].data
    names = set(data.dtype.names or ())
    required = {"x", "y", "z", "opacity", "scale_0", "scale_1", "scale_2"}
    missing = required - names
    if missing:
        raise ValueError(
            "Ce PLY n'est pas un Gaussian Splat (champs manquants : "
            + ", ".join(sorted(missing)) + ")."
        )

    _log(f"{len(data)} splats chargés. Analyse...")
    keep, stats = compute_keep_mask(
        data["x"], data["y"], data["z"], data["opacity"],
        data["scale_0"], data["scale_1"], data["scale_2"],
        **params,
    )

    cleaned = data[keep]
    el = PlyElement.describe(cleaned, "vertex")
    PlyData([el], text=False).write(str(output_path))
    _log(
        f"✅ Nettoyage terminé : {stats['kept']}/{stats['total']} splats conservés "
        f"({stats['removed']} retirés). Écrit dans {output_path}"
    )
    return stats
