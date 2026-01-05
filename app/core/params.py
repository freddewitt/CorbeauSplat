from dataclasses import dataclass, asdict

@dataclass
class ColmapParams:
    """Structure de données pour les paramètres COLMAP"""
    camera_model: str = 'SIMPLE_RADIAL'
    single_camera: bool = True
    max_image_size: int = 3200
    max_num_features: int = 8192
    force_cpu: bool = False
    estimate_affine_shape: bool = False
    domain_size_pooling: bool = True
    max_ratio: float = 0.8
    max_distance: float = 0.7
    cross_check: bool = True
    guided_matching: bool = False
    min_model_size: int = 10
    multiple_models: bool = False
    ba_refine_focal_length: bool = True
    ba_refine_principal_point: bool = False
    ba_refine_extra_params: bool = True
    min_num_matches: int = 15
    matcher_type: str = 'exhaustive' # exhaustive, sequential, vocab_tree
    undistort_images: bool = False
    use_glomap: bool = False
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data):
        # Filtrer les clés inconnues pour éviter les erreurs si le json est vieux
        valid_keys = cls.__annotations__.keys()
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)
