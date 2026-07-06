from dataclasses import dataclass, asdict, fields

FEATURE_TYPES = ['SIFT', 'ALIKED_N16ROT', 'ALIKED_N32']
MATCHING_TYPES = ['SIFT_BRUTEFORCE', 'ALIKED_BRUTEFORCE', 'SIFT_LIGHTGLUE', 'ALIKED_LIGHTGLUE']

FEATURE_TO_DEFAULT_MATCHING = {
    'SIFT': 'SIFT_BRUTEFORCE',
    'ALIKED_N16ROT': 'ALIKED_LIGHTGLUE',
    'ALIKED_N32': 'ALIKED_LIGHTGLUE',
}

COMPATIBLE_MATCHING = {
    'SIFT': ['SIFT_BRUTEFORCE', 'SIFT_LIGHTGLUE'],
    'ALIKED_N16ROT': ['ALIKED_BRUTEFORCE', 'ALIKED_LIGHTGLUE'],
    'ALIKED_N32': ['ALIKED_BRUTEFORCE', 'ALIKED_LIGHTGLUE'],
}

@dataclass
class ColmapParams:
    """Structure de données pour les paramètres COLMAP"""
    camera_model: str = 'SIMPLE_RADIAL'
    single_camera: bool = True
    max_image_size: int = 3200
    max_num_features: int = 8192
    feature_type: str = 'SIFT'
    matching_type: str = 'SIFT_BRUTEFORCE'
    # DSP-SIFT complet : affine_shape + domain_size_pooling maximisent les correspondances
    # (recommandation FAQ COLMAP). Force le calcul CPU — plus lent mais plus robuste.
    estimate_affine_shape: bool = True
    domain_size_pooling: bool = True
    max_ratio: float = 0.8
    max_distance: float = 0.7
    cross_check: bool = True
    guided_matching: bool = False
    ba_refine_focal_length: bool = True
    ba_refine_principal_point: bool = False
    ba_refine_extra_params: bool = True
    min_num_matches: int = 15
    matcher_type: str = 'exhaustive' # exhaustive, sequential, vocab_tree
    sequential_overlap: int = 30
    undistort_images: bool = False
    # Blur filtering: discard frames whose sharpness (variance of Laplacian) falls
    # below blur_factor x the median sharpness. 0 (or filter_blurry=False) disables.
    filter_blurry: bool = False
    blur_factor: float = 0.7
    thermal_throttling: bool = False
    # View graph calibration estimates focal lengths from two-view geometries.
    # Recommended before global_mapper, especially for AI-generated content.
    use_view_graph_calibration: bool = True
    # Ignore watermarks typically found in AI-generated video frames.
    ignore_watermarks: bool = True

    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        # Filtrer les clés inconnues pour éviter les erreurs si le json est vieux
        valid_keys = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)
