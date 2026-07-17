"""
ply_cleaner.py — Nettoyage automatique de fichiers .ply Gaussian Splat.

Retire les artefacts courants produits par la photogrammétrie splatting :
  - Splats quasi-transparents (faible opacité → bruit),
  - Splats surdimensionnés (gaussiennes géantes, ex. "coquilles" de ciel),
  - Outliers spatiaux / floaters loin du nuage principal.

La géométrie et la couleur des splats conservés sont préservées exactement —
nous supprimons uniquement des splats entiers, sans jamais altérer les survivants.
Le fichier original n'est jamais modifié sur place.
"""
from pathlib import Path

import numpy as np

from .base_engine import validate_path_standalone as _validate_path

# Presets de sévérité → (opacity_min sur l'alpha activé, percentile d'échelle, percentile d'outlier)
# Percentile plus élevé = garde plus (plus doux) ; plus bas = supprime plus (plus fort).
PRESETS = {
    "light":  {"opacity_min": 0.05, "scale_pct": 99.9, "outlier_pct": 99.9},
    "medium": {"opacity_min": 0.10, "scale_pct": 99.5, "outlier_pct": 99.5},
    "strong": {"opacity_min": 0.20, "scale_pct": 99.0, "outlier_pct": 99.0},
}


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def compute_clean_mask(x, y, z, opacity, s0, s1, s2,
                       opacity_min=0.10, scale_pct=99.5, outlier_pct=99.5):
    """Calcule un masque booléen de filtrage pour un ensemble de splats Gaussian.

    Les paramètres sont des tableaux numpy 1-D (une entrée par splat). `opacity` est le
    logit brut (pré-sigmoïde) et `s0..s2` sont les échelles logarithmiques, suivant la
    convention PLY 3DGS/Brush. Retourne (keep_mask, stats_dict).
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    z = np.asarray(z, dtype=np.float64)
    opacity = np.asarray(opacity, dtype=np.float64)
    n = len(x)

    # 1. Opacité — supprime les splats quasi-invisibles (bruit).
    alpha = _sigmoid(opacity)
    m_op = alpha >= opacity_min

    # 2. Échelle — supprime les gaussiennes surdimensionnées (coquilles ciel / gros floaters).
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

    # 3. Outliers spatiaux — supprime les splats loin du centre robuste du nuage.
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
    """Retourne le dictionnaire de paramètres de nettoyage pour un nom de preset,
    en appliquant les surcharges."""
    params = dict(PRESETS.get(strength, PRESETS["medium"]))
    if overrides:
        params.update({k: v for k, v in overrides.items() if v is not None})
    return params


def clean_ply(input_path, output_path, strength="medium", overrides=None, log=None):
    """Nettoie un PLY Gaussian Splat et écrit le résultat dans output_path.

    Retourne un dictionnaire de statistiques. Lève ValueError si le fichier
    n'est pas un Gaussian Splat.
    """
    from plyfile import PlyData, PlyElement

    def _log(msg):
        if log:
            log(msg)

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
    keep, stats = compute_clean_mask(
        data["x"], data["y"], data["z"], data["opacity"],
        data["scale_0"], data["scale_1"], data["scale_2"],
        **params,
    )

    cleaned = data[keep]
    el = PlyElement.describe(cleaned, "vertex")
    PlyData([el], text=False).write(str(output_path))
    _log(
        f"Nettoyage terminé : {stats['kept']}/{stats['total']} splats conservés "
        f"({stats['removed']} retirés). Écrit dans {output_path}"
    )
    return stats


def clean_ply_batch(input_dir, output_dir, strength="medium", overrides=None, log=None, recursive=False):
    """Nettoie tous les fichiers .ply d'un dossier.

    Retourne une liste de dictionnaires de statistiques, un par fichier traité.

    Paramètres :
    - input_dir : Path ou str — dossier contenant les .ply
    - output_dir : Path ou str — dossier où écrire les fichiers nettoyés
    - recursive : bool — si True, parcourt récursivement les sous-dossiers
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
        rel = ply_path.relative_to(input_dir)
        out_path = output_dir / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            stats = clean_ply(ply_path, out_path, strength=strength, overrides=overrides, log=log)
            stats["file"] = str(ply_path.name)
            all_stats.append(stats)
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
