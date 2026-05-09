import os
import shutil
import send2trash
import platform
import json
import subprocess
import logging
from pathlib import Path
from typing import Tuple, Any, Optional, Callable
from .base_engine import BaseEngine
from .system import is_apple_silicon, get_optimal_threads, resolve_binary
from .i18n import tr

_IMAGE_EXTS = {'.jpg', '.jpeg', '.png'}


def _first_available_model() -> str:
    try:
        from app.upscayl_models import get_downloaded_models
        from app.upscayl_manager import get_models_dir
        models = get_downloaded_models(get_models_dir())
        return models[0].id if models else ""
    except Exception:
        return ""

class ColmapEngine(BaseEngine):
    """Moteur d'exécution COLMAP indépendant de l'interface graphique"""
    
    def __init__(self, params: Any, input_path: str, output_path: str, input_type: str, fps: int, project_name: str = "Untitled", logger_callback: Optional[Callable] = None, progress_callback: Optional[Callable] = None, status_callback: Optional[Callable] = None, check_cancel_callback: Optional[Callable] = None):
        """Initialise le moteur COLMAP avec les paramètres de configuration."""
        super().__init__("COLMAP", logger_callback)
        self.params = params
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.input_type = input_type
        self.fps = fps
        self.project_name = project_name
        self.is_silicon = is_apple_silicon()
        self.num_threads = get_optimal_threads()
        self._current_process = None
        self.progress = progress_callback if progress_callback else lambda x: None
        self.status = status_callback if status_callback else lambda x: None
        self.check_cancel = check_cancel_callback if check_cancel_callback else lambda: False
        self.logger = logging.getLogger(__name__)
        
        # Resolve binaries
        self.ffmpeg_bin = resolve_binary('ffmpeg') or 'ffmpeg'
        self.colmap_bin = resolve_binary('colmap') or 'colmap'
        self.glomap_bin = resolve_binary('glomap') or 'glomap'
        
        # Pre-load cv2 on the main thread to avoid Bus Error (SIGBUS) 
        try:
            import cv2
            self._cv2_loaded = True
        except ImportError:
            self._cv2_loaded = False
            
        if self.is_silicon:
            self.log(f"Apple Silicon détecté - {self.num_threads} threads optimisés")
        self.log(f"Binaires: {self.colmap_bin}, {self.ffmpeg_bin}, {self.glomap_bin}")

    @property
    def project_path(self) -> Path:
        """Alias pour le chemin de sortie utilisé par les Workers et l'UI."""
        return self.output_path

    def is_cancelled(self) -> bool:
        """Vérifie si l'utilisateur a demandé l'annulation."""
        return self.check_cancel()

    def run(self) -> Tuple[bool, str]:
        """Exécute le pipeline complet de reconstruction."""
        try:
            setup_result = self._validate_and_setup_paths()
            if not setup_result: return False, "Erreur de validation des chemins"
            project_dir, images_dir, checkpoints_dir = setup_result
            
            if not self._process_input(project_dir, images_dir):
                if self.is_cancelled(): return False, tr("USER_CANCELLED")
                return False, "Erreur lors de la preparation de l'entree"

            pipeline_result, msg = self._run_reconstruction_pipeline(project_dir, images_dir)
            return pipeline_result, msg
            
        except Exception as e:
            self.log(f"Erreur lors de l'exécution du pipeline: {e}")
            self.logger.error("Exception in pipeline", exc_info=True)
            if self.is_cancelled(): return False, "Arrete par l'utilisateur"
            return False, "Une erreur est survenue lors du traitement."

    def _validate_and_setup_paths(self) -> Optional[Tuple[Path, Path, Path]]:
        """Valide les chemins d'entrée/sortie et prépare la structure des dossiers."""
        safe_output = self.validate_path(str(self.output_path))
        if not safe_output:
            self.log("Chemin de sortie non sécurisé")
            return None
        self.output_path = safe_output
        
        if ".." in self.project_name or "/" in self.project_name or "\\" in self.project_name:
            self.log("Nom de projet invalide")
            return None

        project_dir = self.output_path / self.project_name
        images_dir = project_dir / "images"
        checkpoints_dir = project_dir / "checkpoints"
        
        project_dir.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)
        checkpoints_dir.mkdir(parents=True, exist_ok=True)
        
        self.log(f"Préparation du projet dans : {project_dir}")
        
        raw_input = str(self.input_path)
        if "|" in raw_input:
            self.log("Validation de multiples chemins d'entree...")
            for p in raw_input.split("|"):
                if not self.validate_path(p.strip()):
                    self.log(f"Chemin d'entrée non sécurisé : {p}")
                    return None
            
            first_path = Path(raw_input.split("|")[0].strip())
            if not first_path.exists():
                self.log(f"Entrée introuvable: {first_path}")
                return None
        else:
            if not self.validate_path(raw_input):
                 self.log(f"Chemin d'entrée non sécurisé: {raw_input}")
                 return None
            if not self.input_path.exists():
                 self.log(f"Entrée introuvable: {self.input_path}")
                 return None

        return project_dir, images_dir, checkpoints_dir

    def _process_input(self, project_dir: Path, images_dir: Path) -> bool:
        """Prépare les images sources (extraction vidéo ou copie)."""
        self.status(tr("status_prep_images", "Préparation des visuels..."))
        if not self._prepare_images(images_dir):
            return False
        
        upscale_conf = getattr(self, 'upscale_config', None)
        if upscale_conf and upscale_conf.get("active", False):
            self.status(tr("status_upscaling", "Upscaling des images..."))
            if not self._run_upscale(project_dir, images_dir):
                return False

        if not self._check_and_normalize_resolution(images_dir):
            return False
            
        return True

    def _run_reconstruction_pipeline(self, project_dir: Path, images_dir: Path) -> Tuple[bool, str]:
        """Exécute les étapes de reconstruction COLMAP."""
        database_path = project_dir / "database.db"
        sparse_dir = project_dir / "sparse"
        sparse_dir.mkdir(exist_ok=True)

        # Always start from a fresh database to avoid SQLite schema incompatibilities
        # (especially between COLMAP and GLOMAP's bundled SQLite versions).
        for db_file in [database_path,
                        database_path.with_suffix(".db-wal"),
                        database_path.with_suffix(".db-shm")]:
            if db_file.exists():
                db_file.unlink(missing_ok=True)
                self.log(f"Base de données précédente supprimée : {db_file.name}")

        self.progress(25)
        
        if self.is_cancelled(): return False, tr("USER_CANCELLED")
        self.status(tr("status_feature_extraction", "Analyse des images en cours..."))    
        if not self.feature_extraction(str(database_path), str(images_dir)):
            return False, "Échec extraction features"
            
        self.progress(50)
        
        if self.is_cancelled(): return False, tr("USER_CANCELLED")
        self.status(tr("status_feature_matching", "Recherche des points communs..."))
        if not self.feature_matching(str(database_path)):
            return False, "Échec matching"
            
        self.progress(75)
        
        if self.is_cancelled(): return False, tr("USER_CANCELLED")

        # GLOMAP's bundled SQLite does not support WAL journal mode created by
        # recent COLMAP versions. Convert the database to DELETE mode before
        # handing it off to GLOMAP.
        if self.params.use_glomap:
            self._convert_db_journal_mode(database_path)

        self.status(tr("status_reconstruction", "Création de la scène 3D..."))
        if not self.mapper(str(database_path), str(images_dir), str(sparse_dir)):
            return False, "Échec reconstruction"
            
        self.progress(90)
        
        if self.params.undistort_images:
            if self.is_cancelled(): return False, tr("USER_CANCELLED")
            dense_dir = project_dir / "dense"
            dense_dir.mkdir(exist_ok=True)
            self.status(tr("status_undistorting", "Correction optique des images..."))
            if not self.image_undistorter(str(images_dir), str(sparse_dir), str(dense_dir)):
                return False, "Echec undistortion"
                
        self.progress(95)
        
        if not self.is_cancelled():
            self.status(tr("status_ready", "Traitement terminé !"))
            self.create_brush_config(project_dir, images_dir, sparse_dir)
            self.progress(100)
            return True, f"Dataset cree: {project_dir}"
            
        return False, "Arrete par l'utilisateur"

    def _prepare_images(self, images_dir: Path) -> bool:
        """Gère l'extraction vidéo ou la copie d'images."""
        if self.input_type == "video":
            if self.is_cancelled(): return False
                
            video_paths = []
            if self.input_path.is_dir():
                supported_exts = {'.mp4', '.mov', '.avi', '.mkv'}
                video_paths = [
                    f for f in self.input_path.rglob('*') 
                    if f.is_file() and f.suffix.lower() in supported_exts
                ]
                video_paths.sort()
            else:
                video_paths = [Path(p.strip()) for p in str(self.input_path).split("|") if p.strip()]

            total_videos = len(video_paths)
            
            if total_videos == 0:
                self.log(f"Aucune vidéo trouvée dans: {self.input_path}")
                return False
            
            for i, video_path in enumerate(video_paths):
                if self.is_cancelled(): return False
                
                if not video_path.exists():
                    self.log(f"Attention: Video introuvable: {video_path}")
                    continue
                    
                base_name = video_path.stem
                prefix = "".join([c for c in base_name if c.isalnum() or c in ('_', '-')])
                
                self.log(f"Extraction video ({i+1}/{total_videos}): {base_name}")
                
                if not self.extract_frames_from_video(str(video_path), images_dir, prefix=prefix):
                     self.log(f"Echec extraction video: {base_name}")
                     return False
            return True
        else:
            self.log("Copie des images sources vers le dossier de travail...")
            try:
                raw_input = str(self.input_path)
                src_files = []
                
                if "|" in raw_input:
                    paths = [Path(p.strip()) for p in raw_input.split("|") if p.strip()]
                    for p in paths:
                        if p.is_file() and p.suffix.lower() in _IMAGE_EXTS and not p.name.lower().endswith('.mask.png'):
                            src_files.append(p)
                elif self.input_path.is_file():
                    if self.input_path.suffix.lower() in _IMAGE_EXTS and not self.input_path.name.lower().endswith('.mask.png'):
                        src_files.append(self.input_path)
                elif self.input_path.is_dir():
                    if self.input_path.resolve() == images_dir.resolve():
                        self.log("Les images sont déjà dans le dossier de destination. Copie ignorée.")
                        return True
                    src_files = [
                        f for f in self.input_path.rglob('*')
                        if f.is_file()
                        and f.suffix.lower() in _IMAGE_EXTS
                        and not f.name.lower().endswith('.mask.png')
                    ]
                
                total_files = len(src_files)
                self.log(f"{total_files} images trouvées.")
                
                if total_files == 0:
                    return True
                
                for i, file_path in enumerate(src_files):
                    if self.is_cancelled(): return False
                    target_path = images_dir / file_path.name
                    if target_path.exists():
                        counter = 1
                        while True:
                            target_path = images_dir / f"{file_path.parent.name}_{counter}_{file_path.name}"
                            if not target_path.exists():
                                break
                            counter += 1
                        
                    shutil.copy2(file_path, target_path)
                    
                    if i % 10 == 0 or i == total_files - 1:
                        p = 5 + int((i / total_files) * 15)
                        self.progress(p)
                        self.status(f"Copie des images : {i+1} / {total_files}")
                
                self.log(f"✅ {total_files} images copiées vers {images_dir}")
                return True
            except Exception as e:
                self.log(f"Erreur copie images: {e}")
                return False

    def _convert_db_journal_mode(self, database_path: Path):
        """Switch the COLMAP database from WAL to DELETE journal mode.

        Recent COLMAP versions open the database in WAL mode, which GLOMAP's
        bundled SQLite cannot handle. This converts it back to the classic
        rollback-journal mode before GLOMAP reads the file.
        """
        import sqlite3
        try:
            with sqlite3.connect(str(database_path)) as con:
                con.execute("PRAGMA journal_mode=DELETE")
                con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            for wal_file in [database_path.parent / (database_path.name + "-wal"),
                             database_path.parent / (database_path.name + "-shm")]:
                if wal_file.exists():
                    wal_file.unlink()
            self.log("Base de données convertie (WAL → DELETE) pour compatibilité GLOMAP.")
        except Exception as e:
            self.log(f"Avertissement : conversion journal mode échouée : {e}")

    def _run_upscale(self, project_dir: Path, images_dir: Path) -> bool:
        """Gère l'upscaling via upscayl-bin."""
        self.log(f"\n{'='*60}\nUpscaling (upscayl-ncnn)\n{'='*60}")
        if self.is_cancelled(): return False

        try:
            from app.core.upscale_engine import UpscaleEngine
            upscaler = UpscaleEngine(logger_callback=self.log)

            if not upscaler.is_installed():
                self.log("WARNING: upscayl-bin not found. Upscale skipped.")
                return True

            images_sources_dir = project_dir / "images_src"

            if not images_sources_dir.exists():
                self.log(f"Moving originals to {images_sources_dir}...")
                shutil.move(str(images_dir), str(images_sources_dir))
                images_dir.mkdir(parents=True, exist_ok=True)

                model_id    = self.upscale_config.get("model_id") or _first_available_model()
                scale       = self.upscale_config.get("scale", 4)
                out_format  = self.upscale_config.get("format", "png")
                tile        = self.upscale_config.get("tile", 0)
                tta         = self.upscale_config.get("tta", False)
                compression = self.upscale_config.get("compression", 0)

                self.log(f"Upscaling x{scale} with model '{model_id}'...")
                success, msg = upscaler.upscale_folder(
                    input_dir=str(images_sources_dir),
                    output_dir=str(images_dir),
                    model_id=model_id,
                    scale=scale,
                    output_format=out_format,
                    tile=tile,
                    tta=tta,
                    compression=compression,
                    cancel_check=self.is_cancelled,
                )
                if not success:
                    self.log(f"Upscale failed: {msg}")
                    return False
                self.log("Upscale complete.")
            else:
                self.log("'images_src' already exists — upscale already done.")

            return True
            
        except Exception as e:
            self.log(f"Erreur Upscale: {e}")
            return False

    def _check_and_normalize_resolution(self, images_dir: Path) -> bool:
        """Vérifie et normalise la résolution des images."""
        self.log(f"\n{'='*60}\nVérification résolution images\n{'='*60}")

        if not getattr(self, '_cv2_loaded', False):
            self.log("⚠️ OpenCV non disponible — vérification résolution ignorée.")
            return True
            
        import cv2

        files = sorted([
            f for f in images_dir.iterdir()
            if f.is_file() and f.suffix.lower() in _IMAGE_EXTS
        ])

        if len(files) < 2:
            return True

        self.log(f"Analyse de {len(files)} images...")

        cache = {}
        sizes = {}
        for f in files:
            if self.is_cancelled():
                return False
            img = cv2.imread(str(f), cv2.IMREAD_UNCHANGED)
            if img is None:
                self.log(f"⚠️ Lecture impossible: {f.name}")
                continue
            h, w = img.shape[:2]
            cache[f] = img
            sizes[f] = (w, h)

        if not sizes:
            return True

        unique_sizes = set(sizes.values())
        if len(unique_sizes) == 1:
            w, h = next(iter(unique_sizes))
            self.log(f"✅ Résolution uniforme: {w}×{h} px")
            return True

        min_w = min(s[0] for s in unique_sizes)
        min_h = min(s[1] for s in unique_sizes)
        images_to_resize = [(f, s) for f, s in sizes.items() if s != (min_w, min_h)]

        self.log(f"⚠️ {len(unique_sizes)} résolutions différentes détectées.")
        self.log(f"Redimensionnement de {len(images_to_resize)} images → {min_w}×{min_h} px")

        for i, (f, _) in enumerate(images_to_resize):
            if self.is_cancelled():
                return False
            img = cache.get(f)
            if img is None:
                self.log(f"⚠️ Lecture impossible: {f.name}")
                continue
            resized = cv2.resize(img, (min_w, min_h), interpolation=cv2.INTER_AREA)
            cv2.imwrite(str(f), resized)
            if (i + 1) % 10 == 0 or (i + 1) == len(images_to_resize):
                self.log(f"Redimensionnement: {i+1}/{len(images_to_resize)}")
                self.status(f"Ajustement taille : {i+1} / {len(images_to_resize)}")

        self.log(f"✅ {len(images_to_resize)} images redimensionnées vers {min_w}×{min_h} px")
        return True

    def extract_frames_from_video(self, video_path: str, images_dir: Path, prefix: Optional[str] = None) -> Optional[bool]:
        """Extrait les frames d'une vidéo via FFmpeg."""
        base_name = Path(video_path).stem
        self.log(f"\n{'='*60}\nExtraction frames: {Path(video_path).name}\n{'='*60}")
        images_dir.mkdir(parents=True, exist_ok=True)
        
        output_pattern = images_dir / (f'{prefix}_%04d.jpg' if prefix else 'frame_%04d.jpg')
        
        cmd = [self.ffmpeg_bin]
        if self.is_silicon:
            cmd.extend(['-hwaccel', 'videotoolbox'])
        
        cmd.extend([
            '-i', video_path,
            '-vf', f'fps={self.fps}',
            '-qscale:v', '2',
            str(output_pattern)
        ])
        
        def _ffmpeg_parser(line_str: str):
            if 'frame=' in line_str or 'error' in line_str.lower():
                self.log(line_str)
                if 'frame=' in line_str:
                    try:
                        f_num = line_str.split('frame=')[1].strip().split()[0]
                        self.status(f"Extraction {base_name} : image {f_num}")
                    except:
                        pass
                        
        try:
            returncode = self._execute_command(cmd, line_callback=_ffmpeg_parser)
            if self.is_cancelled(): return None
            
            if returncode == 0:
                num_frames = len([f for f in images_dir.iterdir() if f.suffix == '.jpg'])
                self.log(f"{num_frames} frames extraites")
                return True
            else:
                self.log(f"Erreur lors de l'extraction")
                return None
        except Exception as e:
            self.log(f"Erreur: {str(e)}")
            return False

    def run_command(self, cmd: list, description: str, status_prefix: Optional[str] = None) -> bool:
        """Exécute une commande système avec logging et callback de statut."""
        self.log(f"\n{'='*60}\n{description}\n{'='*60}")
        
        env = os.environ.copy()
        if self.is_silicon:
            env['OMP_NUM_THREADS'] = str(self.num_threads)
            env['VECLIB_MAXIMUM_THREADS'] = str(self.num_threads)
            env['OPENBLAS_NUM_THREADS'] = str(self.num_threads)
            
        def _colmap_parser(line_str: str):
            self.log(line_str)
            if status_prefix:
                if "Processed file" in line_str:
                    parts = line_str.split("Processed file")
                    if len(parts) > 1:
                        self.status(f"{status_prefix} : image {parts[1].strip()}")
                elif "Matching block" in line_str:
                    parts = line_str.split("Matching block")
                    if len(parts) > 1:
                        self.status(f"{status_prefix} : bloc {parts[1].strip()}")
                elif "Registering image" in line_str:
                    parts = line_str.split("Registering image")
                    if len(parts) > 1:
                        img_info = parts[1].split('(')[0].strip()
                        self.status(f"{status_prefix} : ajout image {img_info}")
                elif "Bundle adjustment report" in line_str:
                    self.status(f"{status_prefix} : optimisation globale...")
                elif "Undistorting image" in line_str:
                    parts = line_str.split("Undistorting image")
                    if len(parts) > 1:
                        self.status(f"{status_prefix} : image {parts[1].strip()}")
                        
        try:
            returncode = self._execute_command(cmd, env=env, line_callback=_colmap_parser)
            if self.is_cancelled(): return False
                
            if returncode == 0:
                self.log(f"{description} termine")
                return True
            else:
                self.log(f"{description} echoue")
                return False
                
        except FileNotFoundError:
            self.log(f"COLMAP non trouve. Installez avec: brew install colmap")
            return False

    def feature_extraction(self, database_path: str, images_dir: str) -> bool:
        """Exécute l'extraction des features SIFT."""
        cmd = [
            self.colmap_bin, 'feature_extractor',
            '--database_path', database_path,
            '--image_path', images_dir,
            '--ImageReader.camera_model', self.params.camera_model,
            '--ImageReader.single_camera', '1' if self.params.single_camera else '0',
            '--FeatureExtraction.num_threads', str(self.num_threads),
            '--FeatureExtraction.max_image_size', str(self.params.max_image_size),
            '--SiftExtraction.max_num_features', str(self.params.max_num_features),
            '--SiftExtraction.estimate_affine_shape', '1' if self.params.estimate_affine_shape else '0',
            '--SiftExtraction.domain_size_pooling', '1' if self.params.domain_size_pooling else '0',
        ]
        return self.run_command(cmd, "Extraction des features", status_prefix="Analyse")

    def feature_matching(self, database_path: str) -> bool:
        """Exécute le matching des features."""
        if self.params.matcher_type == 'sequential':
            cmd = [
                self.colmap_bin, 'sequential_matcher',
                '--database_path', database_path,
                '--FeatureMatching.num_threads', str(self.num_threads),
                '--SiftMatching.max_ratio', str(self.params.max_ratio),
                '--SiftMatching.max_distance', str(self.params.max_distance),
                '--SiftMatching.cross_check', '1' if self.params.cross_check else '0',
            ]
            description = "Matching Sequentiel"
        else:
            cmd = [
                self.colmap_bin, 'exhaustive_matcher',
                '--database_path', database_path,
                '--FeatureMatching.num_threads', str(self.num_threads),
                '--SiftMatching.max_ratio', str(self.params.max_ratio),
                '--SiftMatching.max_distance', str(self.params.max_distance),
                '--SiftMatching.cross_check', '1' if self.params.cross_check else '0',
            ]
            description = "Matching Exhaustif"
            
        return self.run_command(cmd, description, status_prefix="Comparaison")

    def mapper(self, database_path: str, images_dir: str, sparse_dir: Path) -> bool:
        """Exécute la reconstruction 3D (Mapper)."""
        if self.params.use_glomap:
            self.log("Utilisation de GLOMAP pour la reconstruction...")
            cmd = [
                self.glomap_bin, 'mapper',
                '--database_path', database_path,
                '--image_path', images_dir,
                '--output_path', str(sparse_dir)
            ]
            return self.run_command(cmd, "Reconstruction 3D (GLOMAP)", status_prefix="Reconstruction GLOMAP")
        else:
            cmd = [
                self.colmap_bin, 'mapper',
                '--database_path', database_path,
                '--image_path', images_dir,
                '--output_path', str(sparse_dir),
                '--Mapper.num_threads', str(self.num_threads),
                '--Mapper.min_model_size', str(self.params.min_model_size),
                '--Mapper.multiple_models', '1' if self.params.multiple_models else '0',
                '--Mapper.ba_refine_focal_length', '1' if self.params.ba_refine_focal_length else '0',
                '--Mapper.ba_refine_principal_point', '1' if self.params.ba_refine_principal_point else '0',
                '--Mapper.ba_refine_extra_params', '1' if self.params.ba_refine_extra_params else '0',
                '--Mapper.min_num_matches', str(self.params.min_num_matches),
            ]
            return self.run_command(cmd, "Reconstruction 3D (COLMAP)", status_prefix="Reconstruction 3D")

    def image_undistorter(self, images_dir: str, sparse_dir: str, output_dir: str) -> bool:
        """Exécute l'undistortion des images."""
        input_path = Path(sparse_dir) / "0"
        cmd = [
            self.colmap_bin, 'image_undistorter',
            '--image_path', images_dir,
            '--input_path', str(input_path),
            '--output_path', output_dir,
            '--output_type', 'COLMAP',
            '--max_image_size', str(self.params.max_image_size),
        ]
        return self.run_command(cmd, "Undistortion des images", status_prefix="Correction optique")

    def create_brush_config(self, output_dir: Path, images_dir: Path, sparse_dir: Path):
        """Génère le fichier de configuration pour Brush."""
        if self.params.undistort_images:
            final_images_path = output_dir / "dense" / "images"
            final_sparse_path = output_dir / "dense" / "sparse"
            self.log("Utilisation des images et reconstruction non-distordues pour Brush")
        else:
            final_images_path = images_dir
            final_sparse_path = sparse_dir / "0"
            
        config = {
            "dataset_type": "colmap",
            "images_path": str(final_images_path),
            "sparse_path": str(final_sparse_path),
            "created_with": "CorbeauSplat macOS",
            "architecture": platform.machine(),
            "optimized_for": "Apple Silicon" if self.is_silicon else "x86_64",
            "parameters": self.params.to_dict()
        }
        config_path = output_dir / "brush_config.json"
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        self.log(f"Configuration Brush créée: {config_path}")
        
    def stop(self):
        """Arrête le processus en cours."""
        super().stop()

    @staticmethod
    def delete_project_content(target_path: Path) -> Tuple[bool, str]:
        """Supprime le contenu d'un dossier de projet de manière sécurisée."""
        safe_path = Path(target_path).resolve()
        if str(safe_path) == "/" or str(safe_path) == str(Path.home()):
             return False, "Tentative de suppression critique bloquée par sécurité."

        if not target_path.exists():
            return False, "Le dossier n'existe pas"
            
        try:
            for item in target_path.iterdir():
                if item.name == "images":
                    continue
                try:
                    send2trash.send2trash(str(item))
                except Exception as e:
                    logging.getLogger(__name__).error("Failed to trash %s. Reason: %s", item, e)
            return True, "Contenu mis à la corbeille"
        except Exception as e:
            logging.getLogger(__name__).error("Error during project cleanup: %s", e)
            return False, str(e)
