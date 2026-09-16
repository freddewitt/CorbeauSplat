"""
ply_cleaner.py — automatic cleanup of Gaussian Splat .ply files.

Removes the artefacts splatting photogrammetry commonly produces:
  - near-transparent splats (low opacity → noise),
  - oversized splats (giant gaussians, e.g. sky "shells"),
  - spatial outliers / floaters far from the main cloud.

Geometry and colour of the splats kept are preserved exactly — whole splats are
dropped, survivors are never altered. Output is written to a temporary file and
moved into place atomically, so a failure mid-write cannot destroy the input,
even when input and output are the same path.
"""
import os
import tempfile
from pathlib import Path

import numpy as np

from .base_engine import validate_path_standalone as _validate_path


class CleaningCancelled(Exception):
    """Raised when a caller's `cancel_check` asks to stop mid-cleaning."""

# Severity presets → (opacity_min on the activated alpha, scale percentile, outlier percentile)
# Higher percentile = keeps more (gentler); lower = removes more (stronger).
PRESETS = {
    "light":  {"opacity_min": 0.05, "scale_pct": 99.9, "outlier_pct": 99.9},
    "medium": {"opacity_min": 0.10, "scale_pct": 99.5, "outlier_pct": 99.5},
    "strong": {"opacity_min": 0.20, "scale_pct": 99.0, "outlier_pct": 99.0},
}


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def compute_clean_mask(x, y, z, opacity, s0, s1, s2,
                       opacity_min=0.10, scale_pct=99.5, outlier_pct=99.5):
    """Compute a boolean filter mask for a set of Gaussian splats.

    Parameters are 1-D numpy arrays (one entry per splat). `opacity` is the raw
    logit (pre-sigmoid) and `s0..s2` are log scales, following the 3DGS/Brush PLY
    convention. Returns (keep_mask, stats_dict).
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    z = np.asarray(z, dtype=np.float64)
    opacity = np.asarray(opacity, dtype=np.float64)
    n = len(x)

    # 1. Opacity — drop near-invisible splats (noise).
    alpha = _sigmoid(opacity)
    m_op = alpha >= opacity_min

    # 2. Scale — drop oversized gaussians (sky shells / large floaters).
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
    """Return the cleaning parameters for a preset name, applying overrides."""
    params = dict(PRESETS.get(strength, PRESETS["medium"]))
    if overrides:
        params.update({k: v for k, v in overrides.items() if v is not None})
    return params


# plyfile materialises the whole vertex array in memory; the mask and the
# filtered copy add roughly as much again. Four times the file size is a
# deliberately rough upper bound — enough to warn before the OS kills the app.
_MEMORY_FACTOR = 4


def _warn_if_memory_tight(input_path, log):
    """Log a warning when the file looks too large for the RAM available.

    Advisory only: get_memory_info() reports what macOS considers available at
    this instant, which the compressor can change under us. Refusing to run on
    that basis would block legitimate cleanings, so we warn and proceed.
    """
    from app.core.system import get_memory_info

    try:
        size = Path(input_path).stat().st_size
    except OSError:
        return

    available = get_memory_info().get("available", 0)
    if not available or size * _MEMORY_FACTOR <= available:
        return

    log(
        f"AVERTISSEMENT : ce PLY fait {size / 1e9:.1f} Go et le nettoyage doit le charger "
        f"entièrement en mémoire (~{size * _MEMORY_FACTOR / 1e9:.1f} Go nécessaires, "
        f"{available / 1e9:.1f} Go disponibles). L'application peut être arrêtée par le "
        f"système. Fermez d'autres applications ou nettoyez un fichier plus petit."
    )


def clean_ply(input_path, output_path, strength="medium", overrides=None, log=None, cancel_check=None):
    """Clean a Gaussian Splat PLY and write the result to output_path.

    Returns a statistics dictionary. Raises ValueError if the file is not a
    Gaussian Splat, and CleaningCancelled if `cancel_check` returns True at one
    of the checkpoints around the long steps. Reading and writing are single
    plyfile calls and cannot be interrupted once started — cancellation takes
    effect between stages, not within them.

    Writing goes through a temporary file in the destination folder followed by
    an atomic replace, so input_path == output_path is safe.
    """
    from plyfile import PlyData, PlyElement

    def _log(msg):
        if log:
            log(msg)

    def _check_cancelled():
        if cancel_check and cancel_check():
            raise CleaningCancelled()

    # Validate paths before any I/O
    safe_in = _validate_path(input_path)
    if safe_in is None:
        raise ValueError(f"Chemin d'entrée non autorisé: {input_path}")
    safe_out = _validate_path(output_path) or _validate_path(str(Path(output_path).parent))
    if safe_out is None:
        raise ValueError(f"Chemin de sortie non autorisé: {output_path}")
    input_path = safe_in
    output_path = safe_out

    params = resolve_params(strength, overrides)
    _check_cancelled()
    _warn_if_memory_tight(input_path, _log)
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

    _check_cancelled()
    _log(f"{len(data)} splats chargés. Analyse...")
    keep, stats = compute_clean_mask(
        data["x"], data["y"], data["z"], data["opacity"],
        data["scale_0"], data["scale_1"], data["scale_2"],
        **params,
    )

    _check_cancelled()
    cleaned = data[keep]
    # Keep every other element of the source file (e.g. a camera or chunk
    # element): only the vertex list is filtered, the rest passes through.
    elements = [
        PlyElement.describe(cleaned, "vertex") if element.name == "vertex" else element
        for element in ply.elements
    ]
    _write_atomically(PlyData(elements, text=False), output_path)
    _log(
        f"Nettoyage terminé : {stats['kept']}/{stats['total']} splats conservés "
        f"({stats['removed']} retirés). Écrit dans {output_path}"
    )
    return stats


def _write_atomically(ply_data, output_path):
    """Write `ply_data` to a sibling temporary file, then move it into place.

    The destination only ever goes from its old contents to the complete new
    ones. A crash or a full disk mid-write leaves the original untouched.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(suffix=".ply.tmp", dir=str(output_path.parent))
    os.close(fd)
    try:
        ply_data.write(tmp_name)
        os.replace(tmp_name, str(output_path))
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def clean_ply_batch(input_dir, output_dir, strength="medium", overrides=None, log=None, recursive=False,
                    cancel_check=None):
    """Clean every .ply file in a folder.

    Returns a list of statistics dictionaries, one per file processed.

    Parameters:
    - input_dir: Path or str — folder holding the .ply files
    - output_dir: Path or str — folder to write the cleaned files to
    - recursive: bool — if True, walks subfolders
    - cancel_check: callable or None — polled between files and inside each one;
      when it returns True the run stops and the stats gathered so far are returned
    """
    safe_in = _validate_path(input_dir)
    safe_out = _validate_path(output_dir) or _validate_path(str(Path(output_dir).parent))
    if safe_in is None:
        raise ValueError(f"Chemin d'entrée non autorisé: {input_dir}")
    if safe_out is None:
        raise ValueError(f"Chemin de sortie non autorisé: {output_dir}")
    input_dir = safe_in
    output_dir = safe_out
    output_dir.mkdir(parents=True, exist_ok=True)

    pattern = "**/*.ply" if recursive else "*.ply"
    ply_files = sorted(f for f in input_dir.glob(pattern) if not f.name.startswith('.'))

    if not ply_files:
        msg = f"Aucun fichier .ply trouvé dans {input_dir}"
        if log:
            log(msg)
        raise ValueError(msg)

    if log:
        log(f"{len(ply_files)} fichier(s) .ply trouvé(s) dans {input_dir}. Début du nettoyage...")

    all_stats = []
    for ply_path in ply_files:
        if cancel_check and cancel_check():
            if log:
                log("Nettoyage annulé par l'utilisateur.")
            break

        rel = ply_path.relative_to(input_dir)
        out_path = output_dir / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            stats = clean_ply(ply_path, out_path, strength=strength, overrides=overrides, log=log,
                              cancel_check=cancel_check)
            stats["file"] = str(ply_path.name)
            all_stats.append(stats)
        except CleaningCancelled:
            if log:
                log("Nettoyage annulé par l'utilisateur.")
            break
        except ValueError as e:
            if log:
                log(f"⚠️  {ply_path.name}: ignoré ({e})")
            all_stats.append({"file": str(ply_path.name), "error": str(e)})
        except Exception as e:
            if log:
                log(f"❌  {ply_path.name}: erreur ({e})")
            all_stats.append({"file": str(ply_path.name), "error": str(e)})

    if log:
        success = sum(1 for s in all_stats if "error" not in s)
        failed = len(all_stats) - success
        log(f"Nettoyage par lots terminé : {success} réussis, {failed} échoués.")

    return all_stats
