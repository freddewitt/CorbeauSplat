from dataclasses import asdict, dataclass, fields

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

def blur_factor_from_strength(strength: str) -> float:
    """Convert a textual strength (light/medium/strong) into a COLMAP blur factor."""
    return {"light": 0.5, "medium": 0.7, "strong": 0.9}.get(strength, 0.7)


@dataclass
class ColmapParams:
    """Data structure for the COLMAP parameters"""
    camera_model: str = 'SIMPLE_RADIAL'
    single_camera: bool = True
    max_image_size: int = 3200
    max_num_features: int = 8192
    feature_type: str = 'SIFT'
    matching_type: str = 'SIFT_BRUTEFORCE'
    # Full DSP-SIFT: affine_shape + domain_size_pooling maximise the matches
    # (COLMAP FAQ recommendation). Forces CPU computation — slower but more robust.
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
    # Source images outside JPEG/PNG (HEIC, TIFF, BMP, WebP…) are converted on
    # ingest so every downstream tool can read them: "png" (lossless, default),
    # "jpeg" (quality 95) or "off" to copy them untouched.
    image_convert_format: str = 'png'

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        # Filter unknown keys to avoid errors when the json is old
        valid_keys = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)
