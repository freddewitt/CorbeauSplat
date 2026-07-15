"""Construction des commandes CLI COLMAP à partir de ColmapParams.

Responsabilité isolée hors de ColmapEngine : traduire les paramètres en
argv COLMAP (flags SIFT/ALIKED, sequential/exhaustive/vocab_tree, etc.).
Fonctions pures — aucune exécution de processus, aucun état moteur.
L'orchestration du pipeline (enchaînement des étapes, décision de repli
global_mapper → mapper incrémental) reste dans ColmapEngine.
"""
from pathlib import Path
from typing import Any, Optional, Tuple


def build_feature_extraction_command(
    colmap_bin: str,
    database_path: str,
    images_dir: str,
    params: Any,
    num_threads: int,
    image_list_path: Optional[Path] = None,
) -> Tuple[list, str]:
    """Commande d'extraction des features (SIFT ou ALIKED)."""
    feat_type = getattr(params, 'feature_type', 'SIFT')
    cmd = [
        colmap_bin, 'feature_extractor',
        '--database_path', database_path,
        '--image_path', images_dir,
        '--ImageReader.camera_model', params.camera_model,
        '--ImageReader.single_camera', '1' if params.single_camera else '0',
        '--FeatureExtraction.num_threads', str(num_threads),
        '--FeatureExtraction.max_image_size', str(params.max_image_size),
        '--FeatureExtraction.type', feat_type,
    ]
    if feat_type == 'SIFT':
        cmd.extend([
            '--SiftExtraction.max_num_features', str(params.max_num_features),
            '--SiftExtraction.estimate_affine_shape', '1' if params.estimate_affine_shape else '0',
            '--SiftExtraction.domain_size_pooling', '1' if params.domain_size_pooling else '0',
        ])
    else:
        cmd.extend([
            '--AlikedExtraction.max_num_features', str(params.max_num_features),
        ])
    if image_list_path:
        cmd.extend(['--image_list_path', str(image_list_path)])
    return cmd, f"Extraction des features ({feat_type})"


def build_feature_matching_command(
    colmap_bin: str,
    database_path: str,
    params: Any,
    num_threads: int,
) -> Tuple[list, str]:
    """Commande de matching des features (sequential/vocab_tree/exhaustive,
    bruteforce ou LightGlue selon le type de features)."""
    match_type = getattr(params, 'matching_type', 'SIFT_BRUTEFORCE')
    feat_type = getattr(params, 'feature_type', 'SIFT')

    if params.matcher_type == 'sequential':
        cmd = [
            colmap_bin, 'sequential_matcher',
            '--database_path', database_path,
            '--FeatureMatching.num_threads', str(num_threads),
            '--FeatureMatching.type', match_type,
            '--FeatureMatching.guided_matching', '1' if params.guided_matching else '0',
            '--SequentialMatching.overlap', str(params.sequential_overlap),
            '--SequentialMatching.quadratic_overlap', '1',
        ]
        # Loop detection ferme les boucles quand la caméra repasse sur une zone déjà
        # filmée (tour d'objet, pièce en boucle) — évite dérive et fantômes. COLMAP
        # télécharge et met en cache l'arbre de vocabulaire au 1er usage. L'arbre est
        # basé SIFT : on ne l'active que pour les features SIFT (incompatible ALIKED).
        if feat_type == 'SIFT':
            cmd.extend(['--SequentialMatching.loop_detection', '1'])
        description = f"Matching Sequentiel ({match_type})"
    elif params.matcher_type == 'vocab_tree':
        # Vocab tree : matching par similarité visuelle, adapté aux grandes collections
        # de photos non ordonnées (bien plus rapide qu'exhaustif au-delà de ~500 images).
        # COLMAP télécharge/met en cache l'arbre de vocabulaire (SIFT) au 1er usage.
        cmd = [
            colmap_bin, 'vocab_tree_matcher',
            '--database_path', database_path,
            '--FeatureMatching.num_threads', str(num_threads),
            '--FeatureMatching.type', match_type,
            '--FeatureMatching.guided_matching', '1' if params.guided_matching else '0',
        ]
        description = f"Matching Vocab Tree ({match_type})"
    else:
        cmd = [
            colmap_bin, 'exhaustive_matcher',
            '--database_path', database_path,
            '--FeatureMatching.num_threads', str(num_threads),
            '--FeatureMatching.type', match_type,
            '--FeatureMatching.guided_matching', '1' if params.guided_matching else '0',
        ]
        description = f"Matching Exhaustif ({match_type})"

    # Add algo-specific matching flags
    if match_type == 'SIFT_BRUTEFORCE':
        cmd.extend([
            '--SiftMatching.max_ratio', str(params.max_ratio),
            '--SiftMatching.max_distance', str(params.max_distance),
            '--SiftMatching.cross_check', '1' if params.cross_check else '0',
        ])
    elif feat_type.startswith('ALIKED'):
        cmd.extend([
            '--AlikedMatching.min_cossim', '0.85',
        ])
    # LightGlue types carry their own matching — no extra flags needed

    return cmd, description


def build_global_mapper_command(
    colmap_bin: str,
    database_path: str,
    images_dir: str,
    sparse_dir: Path,
    params: Any,
    num_threads: int,
) -> list:
    """Commande de reconstruction 3D via le mapper global (GLOMAP, COLMAP 4.0+)."""
    return [
        colmap_bin, 'global_mapper',
        '--database_path', database_path,
        '--image_path', images_dir,
        '--output_path', str(sparse_dir),
        '--GlobalMapper.num_threads', str(num_threads),
        '--GlobalMapper.min_num_matches', str(params.min_num_matches),
        '--GlobalMapper.ignore_watermarks', '1' if params.ignore_watermarks else '0',
        '--GlobalMapper.ba_refine_focal_length', '1' if params.ba_refine_focal_length else '0',
        '--GlobalMapper.ba_refine_principal_point', '1' if params.ba_refine_principal_point else '0',
        '--GlobalMapper.ba_refine_extra_params', '1' if params.ba_refine_extra_params else '0',
    ]


def build_incremental_mapper_command(
    colmap_bin: str,
    database_path: str,
    images_dir: str,
    sparse_dir: Path,
    params: Any,
    num_threads: int,
) -> list:
    """Commande de reconstruction 3D via le mapper incrémental (repli si le
    mapper global ne produit pas de modèle exploitable)."""
    return [
        colmap_bin, 'mapper',
        '--database_path', database_path,
        '--image_path', images_dir,
        '--output_path', str(sparse_dir),
        '--Mapper.num_threads', str(num_threads),
        '--Mapper.min_num_matches', str(params.min_num_matches),
        '--Mapper.ignore_watermarks', '1' if params.ignore_watermarks else '0',
        '--Mapper.ba_refine_focal_length', '1' if params.ba_refine_focal_length else '0',
        '--Mapper.ba_refine_principal_point', '1' if params.ba_refine_principal_point else '0',
        '--Mapper.ba_refine_extra_params', '1' if params.ba_refine_extra_params else '0',
    ]


def build_image_undistorter_command(
    colmap_bin: str,
    images_dir: str,
    sparse_dir: str,
    output_dir: str,
    params: Any,
) -> Tuple[list, str]:
    """Commande d'undistortion des images à partir du modèle sparse."""
    input_path = Path(sparse_dir) / "0"
    cmd = [
        colmap_bin, 'image_undistorter',
        '--image_path', images_dir,
        '--input_path', str(input_path),
        '--output_path', output_dir,
        '--output_type', 'COLMAP',
        '--max_image_size', str(params.max_image_size),
    ]
    return cmd, "Undistortion des images"
