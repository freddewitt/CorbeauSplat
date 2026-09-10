import shutil
import sys
from pathlib import Path

from .base_engine import BaseEngine
from .system import get_optimal_threads, is_apple_silicon, resolve_binary, resolve_project_root

# Path to the dedicated nerfstudio venv
_VENV_4DGS = resolve_project_root() / ".venv_4dgs"


def get_venv_4dgs_python():
    """Returns path to python executable in .venv_4dgs"""
    if sys.platform == "win32":
        return _VENV_4DGS / "Scripts" / "python.exe"
    return _VENV_4DGS / "bin" / "python"


def _get_ns_process_data_path():
    """Returns path to ns-process-data in the 4DGS venv"""
    if sys.platform == "win32":
        return _VENV_4DGS / "Scripts" / "ns-process-data.exe"
    return _VENV_4DGS / "bin" / "ns-process-data"


class FourDGSEngine(BaseEngine):
    """
    Moteur pour la préparation de datasets 4DGS (Video -> COLMAP -> Nerfstudio).
    Nerfstudio est isolé dans un venv dédié (.venv_4dgs).
    """
    def __init__(self, logger_callback=None, status_callback=None):
        super().__init__("4DGS", logger_callback)
        self.status = status_callback if status_callback else lambda x: None

        # Resolve binaries
        self.ffmpeg = resolve_binary("ffmpeg") or "ffmpeg"
        self.colmap = resolve_binary("colmap") or "colmap"
        self.venv_python = get_venv_4dgs_python()
        self.ns_process_data = str(_get_ns_process_data_path())
        # Set by the GUI (mirrors ColmapEngine.upscale_config) — see upscale_dataset_images()
        self.upscale_config = None

    def check_nerfstudio(self):
        """Vérifie si ns-process-data est disponible dans le venv dédié"""
        ns_path = _get_ns_process_data_path()
        return ns_path.exists()

    def extract_frames(self, video_path, output_dir, fps=5):
        """Extrait les frames d'une vidéo avec ffmpeg"""
        if self.stop_requested:
            return False

        fps = max(1, int(fps))
        out_p = Path(output_dir)
        out_p.mkdir(parents=True, exist_ok=True)

        cmd = [self.ffmpeg]
        if is_apple_silicon():
            cmd.extend(["-hwaccel", "videotoolbox"])

        cmd.extend([
            "-i", str(video_path),
            "-vf", f"fps={fps}",
            "-q:v", "2", # Haute qualité jpeg
            str(out_p / "%05d.jpg")
        ])

        # Template Method : Délégation à _execute_command centralisé
        # Grosses vidéos / disques externes lents : même palier que Brush (4h).
        return self._execute_command(cmd, timeout=14400) == 0

    def _build_static_reference_set(self, images_path, staging_path):
        """Stage a single reference frame per camera for static-scene SfM.

        COLMAP assumes a rigid, static scene: matching frames captured at
        different timesteps of a moving scene breaks that assumption and
        corrupts the reconstruction. Reference multi-view 4DGS pipelines
        (e.g. hustvl/4DGaussians' multipleviewprogress.sh + extractimages.py)
        run SfM on exactly one synchronized frame per camera and reuse those
        poses for every timestep, since the camera rig itself does not move.
        Falls back to ``images_path`` unchanged if it holds no per-camera
        subfolders (flat single-camera dataset).
        """
        cam_dirs = sorted(
            d for d in images_path.iterdir()
            if d.is_dir() and not d.name.endswith("_src")
        ) if images_path.is_dir() else []
        if not cam_dirs:
            return images_path

        if staging_path.exists():
            shutil.rmtree(staging_path)
        staging_path.mkdir(parents=True)

        for cam_dir in cam_dirs:
            frames = sorted(f for f in cam_dir.iterdir() if f.is_file())
            if not frames:
                continue
            reference = frames[0]
            shutil.copy2(reference, staging_path / f"{cam_dir.name}{reference.suffix}")

        self.log(f"Static reference set: {len(cam_dirs)} camera(s), 1 frame each -> {staging_path}")
        return staging_path

    def run_colmap(self, dataset_root, camera_model="OPENCV", single_camera=True,
                   matcher_type="exhaustive", sequential_overlap=10):
        """Lance le pipeline COLMAP : Feature Extractor -> Matcher -> Mapper.

        SfM tourne sur un jeu de référence statique — une frame par caméra,
        cf. ``_build_static_reference_set`` — pas sur l'ensemble des frames
        de toutes les caméras à tous les instants.

        ``camera_model``/``single_camera`` : à ajuster pour un rig multi-caméras
        composé de modèles hétérogènes (le défaut suppose un même modèle pour
        toutes les vues). ``matcher_type="sequential"`` accélère le matching sur
        de longues séquences de frames au prix de l'exhaustivité des paires
        testées ; ``sequential_overlap`` règle le nombre de frames voisines
        comparées dans ce mode."""
        if self.stop_requested:
            return False

        root = Path(dataset_root)
        db_path = root / "database.db"
        images_path = root / "images"
        sparse_path = root / "sparse"
        sparse_path.mkdir(parents=True, exist_ok=True)

        colmap_images_path = self._build_static_reference_set(images_path, root / "colmap_reference_frames")

        # 1. Feature Extraction
        self.log("--- COLMAP: Feature Extraction ---")
        self.status("Extraction des features (COLMAP)...")
        cmd_extract = [
            self.colmap, "feature_extractor",
            "--database_path", str(db_path),
            "--image_path", str(colmap_images_path),
            "--ImageReader.camera_model", camera_model,
            "--ImageReader.single_camera", "1" if single_camera else "0"
        ]

        if self._execute_command(cmd_extract, timeout=14400) != 0:
            return False

        self.log("--- COLMAP: Feature Matching ---")
        self.status("Matching des features...")
        if matcher_type == "sequential":
            cmd_match = [
                self.colmap, "sequential_matcher",
                "--database_path", str(db_path),
                "--SequentialMatching.overlap", str(sequential_overlap),
            ]
        else:
            cmd_match = [
                self.colmap, "exhaustive_matcher",
                "--database_path", str(db_path),
            ]

        if self._execute_command(cmd_match, timeout=14400) != 0:
            return False

        # 3. Mapper
        self.log("--- COLMAP: Mapper (Sparse Reconstruction) ---")
        self.status("Reconstruction 3D (Mapper)...")
        cmd_mapper = [
            self.colmap, "mapper",
            "--database_path", str(db_path),
            "--image_path", str(colmap_images_path),
            "--output_path", str(sparse_path)
        ]

        threads = str(get_optimal_threads())
        cmd_mapper.append(f"--Mapper.num_threads={threads}")

        return self._execute_command(cmd_mapper, timeout=14400) == 0

    def upscale_dataset_images(self, output_dir) -> bool:
        """Upscale extracted camera frames in-place via the shared Upscale engine.

        Runs once per ``<output_dir>/images/cam_XX`` subfolder, before COLMAP or
        ns-process-data consume them. No-op if ``upscale_config`` is not active.
        """
        upscale_conf = self.upscale_config or {}
        if not upscale_conf.get("active", False):
            return True
        if self.stop_requested:
            return False

        from .engine import _first_available_model
        from .upscale_engine import UpscaleEngine

        upscaler = UpscaleEngine(logger_callback=self.log)
        if not upscaler.is_installed():
            self.log("WARNING: upscayl-bin not found. Upscale skipped.")
            return True

        images_root = Path(output_dir) / "images"
        cam_dirs = sorted(d for d in images_root.iterdir() if d.is_dir()) if images_root.is_dir() else []
        if not cam_dirs:
            return True

        model_id    = upscale_conf.get("model_id") or _first_available_model()
        scale       = upscale_conf.get("scale", 4)
        out_format  = upscale_conf.get("format", "png")
        tile        = upscale_conf.get("tile", 0)
        tta         = upscale_conf.get("tta", False)
        compression = upscale_conf.get("compression", 0)

        for cam_dir in cam_dirs:
            if self.stop_requested:
                return False
            src_dir = cam_dir.parent / f"{cam_dir.name}_src"
            if src_dir.exists():
                self.log(f"'{src_dir.name}' already exists — {cam_dir.name} already upscaled.")
                continue

            self.log(f"Upscaling {cam_dir.name} x{scale} with model '{model_id}'...")
            shutil.move(str(cam_dir), str(src_dir))
            cam_dir.mkdir(parents=True, exist_ok=True)
            success, msg = upscaler.upscale_folder(
                input_dir=str(src_dir),
                output_dir=str(cam_dir),
                model_id=model_id,
                scale=scale,
                output_format=out_format,
                tile=tile,
                tta=tta,
                compression=compression,
                cancel_check=lambda: self.stop_requested,
            )
            if not success:
                self.log(f"Upscale failed for {cam_dir.name}: {msg}")
                return False

        self.log("Upscale complete.")
        return True

    def process_dataset(self, videos_dir, output_dir, fps=5, colmap_params=None):
        safe_in = self.validate_path(videos_dir)
        safe_out = self.validate_path(output_dir) or self.validate_path(str(Path(output_dir).parent))
        if safe_in is None:
            self.log(f"SECURITY: Invalid input directory: {videos_dir}")
            return False
        if safe_out is None:
            self.log(f"SECURITY: Invalid output directory: {output_dir}")
            return False
        self.log(f"Scan du dossier : {videos_dir}")
        supported_ext = (".mp4", ".mov", ".avi", ".mkv")
        videos_path = Path(videos_dir)
        videos = sorted([
            f for f in videos_path.iterdir()
            if f.suffix.lower() in supported_ext and not f.name.startswith("._")
        ])

        if not videos:
            self.log("Aucune vidéo trouvée.")
            return False

        self.log(f"Trouvé {len(videos)} vidéos. Début extraction...")

        images_root = Path(output_dir) / "images"
        images_root.mkdir(parents=True, exist_ok=True)

        # 1. Extraction
        for idx, vid_path in enumerate(videos):
            if self.stop_requested:
                return False
            cam_name = f"cam_{idx:02d}"
            cam_dir = images_root / cam_name

            self.log(f"Extraction {vid_path.name} -> {cam_name} ({fps} fps)...")
            self.status(f"Extraction des frames ({vid_path.name})...")
            if not self.extract_frames(vid_path, cam_dir, fps):
                return False

        self.log("Extraction terminée.")

        if not self.upscale_dataset_images(output_dir):
            return False

        if self.check_nerfstudio():
            self.log("ns-process-data détecté (venv_4dgs). Lancement du processing Nerfstudio...")
            self.status("Traitement Nerfstudio en cours...")

            # Use the dedicated venv script
            cmd_ns = [
                self.ns_process_data, "images",
                "--data", str(images_root),
                "--output-dir", str(output_dir),
                "--verbose"
            ]

            if self._execute_command(cmd_ns) != 0:
                self.log("Echec ns-process-data.")
                return False

            return True
        else:
            self.log("Nerfstudio non trouvé. Lancement mode dégradé (COLMAP manuel uniquement).")
            return self.run_colmap(output_dir, **(colmap_params or {}))
