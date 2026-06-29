from dataclasses import asdict, dataclass, fields


@dataclass
class ColmapParams:
    """Structure de données pour les paramètres COLMAP"""
    camera_model: str = 'SIMPLE_RADIAL'
    single_camera: bool = True
    max_image_size: int = 3200
    max_num_features: int = 8192
    force_cpu: bool = False
    estimate_affine_shape: bool = False
    # OFF by default: domain-size-pooling (and affine shape) disable COLMAP's
    # GPU SIFT, falling back to slow CPU extraction. Keep off to use the CUDA GPU.
    domain_size_pooling: bool = False
    max_ratio: float = 0.8
    max_distance: float = 0.7
    cross_check: bool = True
    guided_matching: bool = False
    min_model_size: int = 10
    multiple_models: bool = False
    ba_refine_focal_length: bool = True
    ba_refine_principal_point: bool = False
    ba_refine_extra_params: bool = True
    # GPU-accelerated bundle adjustment (COLMAP 4.1.0 "Caspar" solver). ON by
    # default for speed — only passed to the mapper when the installed COLMAP
    # supports --Mapper.ba_use_gpu, otherwise it is silently skipped (no crash).
    # COLMAP auto-falls back to CPU for small scenes, so it's safe as a default.
    ba_use_gpu: bool = True
    ba_gpu_index: int = -1
    # Bundle-adjustment cost bounds (faster than COLMAP defaults, still safe for a
    # 3DGS target which tolerates sub-pixel pose error). The global BA is the
    # dominant mapper cost on large scenes; these cap its iterations and how often
    # it re-runs. Tunable via config.json if a specific scene needs the slower,
    # higher-accuracy COLMAP defaults (50 / 0.0 / 1.1 / 1.1 / 25).
    ba_global_max_num_iterations: int = 30      # COLMAP default 50
    ba_global_function_tolerance: float = 1e-6  # COLMAP default 0.0 (run all iters)
    ba_global_images_ratio: float = 1.2         # COLMAP default 1.1 (run global BA less often)
    ba_global_points_ratio: float = 1.2         # COLMAP default 1.1
    ba_local_max_num_iterations: int = 20       # COLMAP default 25
    # Refinement passes: each global-BA trigger re-runs BA+filtering up to
    # max_refinements times. This is the dominant cost of the "Retriangulation
    # and Global bundle adjustment" step — capping it is the single biggest
    # in-mapper speed lever. Local BA runs after every image, so its aggregate
    # cost matters too.
    ba_global_max_refinements: int = 3          # COLMAP default 5
    ba_local_max_refinements: int = 1           # COLMAP default 2
    min_num_matches: int = 15
    # Sequential is the fast + correct default for video frames (ordered input):
    # O(n) instead of exhaustive's O(n²). The whole pipeline is video → frames.
    matcher_type: str = 'sequential' # exhaustive, sequential, vocab_tree
    sequential_overlap: int = 30
    # Loop-closure detection for sequential matching: recognises when the camera
    # REVISITS a place (common in video) and matches those frames, so the same
    # location isn't reconstructed twice ("ghost"/duplicate buildings). Needs a
    # vocabulary tree (auto-downloaded); harmless when off.
    loop_detection: bool = True
    undistort_images: bool = False
    use_glomap: bool = False
    # Blur filtering: discard frames whose sharpness (variance of Laplacian) falls
    # below blur_factor × the median sharpness. 0 (or filter_blurry=False) disables.
    filter_blurry: bool = False
    blur_factor: float = 0.7

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        # Filtrer les clés inconnues pour éviter les erreurs si le json est vieux
        valid_keys = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)
