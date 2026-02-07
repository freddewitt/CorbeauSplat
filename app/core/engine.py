import os
import shutil
import concurrent.futures
import send2trash
import platform
import json
import subprocess
from pathlib import Path
from .base_engine import BaseEngine
from .params import ColmapParams
from .system import is_apple_silicon, get_optimal_threads, resolve_binary, get_device

class ColmapEngine(BaseEngine):
    """Moteur d'exécution COLMAP indépendant de l'interface graphique"""
    
    def __init__(self, params, input_path, output_path, input_type, fps, project_name="Untitled", logger_callback=None, progress_callback=None, check_cancel_callback=None):
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
        self.check_cancel = check_cancel_callback if check_cancel_callback else lambda: False
        
        # Resolve binaries
        self.ffmpeg_bin = resolve_binary('ffmpeg') or 'ffmpeg'
        self.colmap_bin = resolve_binary('colmap') or 'colmap'
        self.glomap_bin = resolve_binary('glomap') or 'glomap'
        
        if self.is_silicon:
            self.log(f"Apple Silicon détecté - {self.num_threads} threads optimisés")
        self.log(f"Binaires: {self.colmap_bin}, {self.ffmpeg_bin}, {self.glomap_bin}")

    # log method inherited from BaseEngine
        
    @property
    def project_path(self):
        """Alias for output_path used by Workers and UI"""
        return self.output_path

    def is_cancelled(self):
        return self.check_cancel()

    def run(self):
        """Exécute le pipeline complet"""
        try:
            # Création de la structure Projet
            # [Output] / [ProjectName] / [images, checkpoints, sparse, dense]
            project_dir = self.output_path / self.project_name
            images_dir = project_dir / "images"
            checkpoints_dir = project_dir / "checkpoints"
            
            project_dir.mkdir(parents=True, exist_ok=True)
            images_dir.mkdir(parents=True, exist_ok=True)
            checkpoints_dir.mkdir(parents=True, exist_ok=True)
            
            self.log(f"Préparation du projet dans : {project_dir}")
            
            # Validation Input
            # Note: self.input_path is now a Path object, but video supports pipe strings
            if self.input_type != "video":
                 if not self.input_path.exists():
                     return False, f"Entrée introuvable: {self.input_path}"
            elif not "|" in str(self.input_path) and not self.input_path.exists():
                 return False, f"Vidéo introuvable: {self.input_path}"

            # 1. Preparation des Images (Extraction ou Copie)
            if not self._prepare_images(images_dir):
                return False, "Echec preparation images"
            
            # --- UPSCALE STEP ---
            upscale_conf = getattr(self, 'upscale_config', None)
            if upscale_conf and upscale_conf.get("active", False):
                if not self._run_upscale(project_dir, images_dir):
                    return False, "Echec Upscale"
                
            # Structure de dossiers
            database_path = project_dir / "database.db"
            sparse_dir = project_dir / "sparse"
            sparse_dir.mkdir(exist_ok=True)
            
            self.progress(25)
            
            # 1. Feature Extraction
            if self.is_cancelled(): return False, tr("USER_CANCELLED")
                
            if not self.feature_extraction(str(database_path), str(images_dir)):
                if self.is_cancelled(): return False, tr("USER_CANCELLED")
                return False, "Échec extraction features"
                
            self.progress(50)
            
            # 2. Feature Matching
            if self.is_cancelled(): return False, tr("USER_CANCELLED")
                
            if not self.feature_matching(str(database_path)):
                if self.is_cancelled(): return False, tr("USER_CANCELLED")
                return False, "Échec matching"
                
            self.progress(75)
            
            # 3. Reconstruction
            if self.is_cancelled(): return False, tr("USER_CANCELLED")
                
            if not self.mapper(str(database_path), str(images_dir), str(sparse_dir)):
                if self.is_cancelled(): return False, tr("USER_CANCELLED")
                return False, "Échec reconstruction"
                
            self.progress(90)
            
            # 4. Image Undistortion (Optionnel)
            if self.params.undistort_images:
                if self.is_cancelled(): return False, tr("USER_CANCELLED")
                    
                dense_dir = project_dir / "dense"
                dense_dir.mkdir(exist_ok=True)
                
                if not self.image_undistorter(str(images_dir), str(sparse_dir), str(dense_dir)):
                    if self.is_cancelled(): return False, "Arrete par l'utilisateur"
                    return False, "Echec undistortion"
                    
            self.progress(95)
            
            # Configuration Brush
            if not self.is_cancelled():
                self.create_brush_config(project_dir, images_dir, sparse_dir)
                self.progress(100)
                return True, f"Dataset cree: {project_dir}"
            else:
                return False, "Arrete par l'utilisateur"
            
        except Exception as e:
            if self.is_cancelled(): return False, "Arrete par l'utilisateur"
            return False, str(e)

    def _prepare_images(self, images_dir: Path):
        """Gère l'extraction vidéo ou la copie d'images"""
        if self.input_type == "video":
            if self.is_cancelled(): return False
                
            # Support multi-fichiers séparés par "|"
            video_paths = str(self.input_path).split("|")
            total_videos = len(video_paths)
            
            for i, video_path_str in enumerate(video_paths):
                if self.is_cancelled(): return False
                
                video_path = Path(video_path_str.strip())
                if not video_path.exists():
                    self.log(f"Attention: Video introuvable: {video_path}")
                    continue
                    
                # Prefix based on filename
                base_name = video_path.stem
                prefix = "".join([c for c in base_name if c.isalnum() or c in ('_', '-')])
                
                self.log(f"Extraction video ({i+1}/{total_videos}): {base_name}")
                
                if not self.extract_frames_from_video(str(video_path), images_dir, prefix=prefix):
                     self.log(f"Echec extraction video: {base_name}")
                     return False
            return True
        else:
            # Copie des images (récursive pour supporter les sorties d'extracteurs)
            self.log("Copie des images sources vers le dossier de travail...")
            
            if self.input_path.resolve() == images_dir.resolve():
                self.log("Les images sont déjà dans le dossier de destination. Copie ignorée.")
                return True
            
            try:
                # Recherche récursive de fichiers images, en ignorant les masques (*.mask.png)
                src_files = []
                # On utilise rglob pour la récursivité
                for ext in ('*.jpg', '*.jpeg', '*.png'):
                    for f in self.input_path.rglob(ext):
                        if f.is_file() and not f.name.lower().endswith('.mask.png'):
                            src_files.append(f)
                
                total_files = len(src_files)
                self.log(f"{total_files} images trouvées.")
                
                if total_files == 0:
                    return True # On continue, peut-être qu'elles sont déjà là ou gérées autrement
                
                # Copie
                for i, file_path in enumerate(src_files):
                    if self.is_cancelled(): return False
                    
                    # On évite d'utiliser le chemin relatif du sous-dossier pour simplifier la structure COLMAP
                    # sauf si on veut garder la hiérarchie. Ici COLMAP préfère souvent un dossier plat.
                    target_path = images_dir / file_path.name
                    
                    # Si collision de nom (ex: frame_001.jpg dans deux dossiers différents), on ajoute un préfixe
                    if target_path.exists():
                        target_path = images_dir / f"{file_path.parent.name}_{file_path.name}"
                        
                    shutil.copy2(file_path, target_path)
                    
                    if i % 10 == 0 or i == total_files - 1:
                        p = 5 + int((i / total_files) * 15) # 5-20% range
                        self.progress(p)
                
                self.log(f"✅ {total_files} images copiées vers {images_dir}")
                return True
                    
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    list(executor.map(copy_image, src_files))
                    
                self.log(f"{len(src_files)} images copiees.")
                return True
            except Exception as e:
                self.log(f"Erreur copie images: {e}")
                return False

    def _run_upscale(self, project_dir: Path, images_dir: Path):
        """Gère l'upscaling"""
        self.log(f"\n{'='*60}\nUpscaling (Super-Resolution)\n{'='*60}")
        if self.is_cancelled(): return False
        
        try:
            from app.core.upscale_engine import UpscaleEngine
            upscaler = UpscaleEngine(logger_callback=self.log)
            
            if not upscaler.is_installed():
                 self.log("ATTENTION: Upscale activé mais dépendances manquantes. Ignoré.")
                 return True # Non-fatal
            
            # 1. Move original images to "images_src"
            images_sources_dir = project_dir / "images_src"
            
            if not images_sources_dir.exists():
                self.log(f"Déplacement des originaux vers {images_sources_dir}...")
                shutil.move(str(images_dir), str(images_sources_dir))
                images_dir.mkdir(parents=True, exist_ok=True)
                
                # Perform Upscale
                model_name = self.upscale_config.get("model_name", "RealESRGAN_x4plus")
                tile_size = self.upscale_config.get("tile", 0)
                target_scale = self.upscale_config.get("target_scale", 4)
                face_enhance = self.upscale_config.get("face_enhance", False)
                fp16 = self.upscale_config.get("fp16", False)
                
                upsampler = upscaler.load_model(model_name=model_name, tile=tile_size, target_scale=target_scale, half=fp16)
                if not upsampler:
                    self.log("Echec chargement modele Upscale")
                    return False
                    
                self.log(f"Traitement Upscale (x{target_scale}) en cours...")
                files = sorted([f for f in images_sources_dir.iterdir() if f.is_file() and f.suffix.lower() in ('.jpg', '.png', '.jpeg')])
                
                total = len(files)
                for i, f_path in enumerate(files):
                    if self.is_cancelled(): return False
                    out_p = images_dir / f_path.name
                    
                    upscaler.upscale_image(str(f_path), str(out_p), upsampler, face_enhance=face_enhance)
                    if (i % 5 == 0): self.log(f"Upscale {i+1}/{total}...")
                    
                self.log("Upscale termine.")
            else:
                self.log("Dossier 'images_src' existant. On présume que l'upscale a déjà été fait.")
                
            return True
            
        except Exception as e:
            self.log(f"Erreur Upscale: {e}")
            return False

    def extract_frames_from_video(self, video_path: str, images_dir: Path, prefix=None):
        """Extraction vidéo optimisée"""
        self.log(f"\n{'='*60}\nExtraction frames: {Path(video_path).name}\n{'='*60}")
        images_dir.mkdir(parents=True, exist_ok=True)
        
        # Output pattern
        if prefix:
             output_pattern = images_dir / f'{prefix}_%04d.jpg'
        else:
             output_pattern = images_dir / 'frame_%04d.jpg'
        
        cmd = [self.ffmpeg_bin]
        if self.is_silicon:
            cmd.extend(['-hwaccel', 'videotoolbox'])
        
        cmd.extend([
            '-i', video_path,
            '-vf', f'fps={self.fps}',
            '-qscale:v', '2',
            str(output_pattern)
        ])
        
        try:
            self._current_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )
            
            for line in self._current_process.stdout:
                if self.is_cancelled():
                    self._current_process.terminate()
                    return None
                if 'frame=' in line or 'error' in line.lower():
                    self.log(line.rstrip())
            
            self._current_process.wait()
            
            if self.is_cancelled(): return None
                
            if self._current_process.returncode == 0:
                num_frames = len([f for f in images_dir.iterdir() if f.suffix == '.jpg'])
                self.log(f"{num_frames} frames extraites")
                return True
            else:
                self.log(f"Erreur lors de l'extraction")
                return None
                
        except FileNotFoundError:
            self.log("ffmpeg non trouve. Installez avec: brew install ffmpeg")
            return False
        except Exception as e:
            self.log(f"Erreur: {str(e)}")
            return False
        finally:
            self._current_process = None

    def run_command(self, cmd, description):
        """Exécute une commande avec support d'interruption"""
        self.log(f"\n{'='*60}\n{description}\n{'='*60}")
        
        try:
            env = os.environ.copy()
            if self.is_silicon:
                env['OMP_NUM_THREADS'] = str(self.num_threads)
                env['VECLIB_MAXIMUM_THREADS'] = str(self.num_threads)
                env['OPENBLAS_NUM_THREADS'] = str(self.num_threads)
                
            self._current_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, env=env
            )
            
            for line in self._current_process.stdout:
                if self.is_cancelled():
                    self._current_process.terminate()
                    return False
                self.log(line.rstrip())
                
            self._current_process.wait()
            
            if self.is_cancelled(): return False
                
            if self._current_process.returncode == 0:
                self.log(f"{description} termine")
                return True
            else:
                self.log(f"{description} echoue")
                return False
                
        except FileNotFoundError:
            self.log(f"COLMAP non trouve. Installez avec: brew install colmap")
            return False
        finally:
            self._current_process = None

    def feature_extraction(self, database_path, images_dir):
        cmd = [
            self.colmap_bin, 'feature_extractor',
            '--database_path', database_path,
            '--image_path', images_dir,
            '--ImageReader.camera_model', self.params.camera_model,
            '--ImageReader.single_camera', '1' if self.params.single_camera else '0',
            '--FeatureExtraction.num_threads', str(self.num_threads),
            '--SiftExtraction.max_image_size', str(self.params.max_image_size),
            '--SiftExtraction.max_num_features', str(self.params.max_num_features),
            '--SiftExtraction.estimate_affine_shape', '1' if self.params.estimate_affine_shape else '0',
            '--SiftExtraction.domain_size_pooling', '1' if self.params.domain_size_pooling else '0',
        ]
        return self.run_command(cmd, "Extraction des features")

    def feature_matching(self, database_path):
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
            
        return self.run_command(cmd, description)

    def mapper(self, database_path, images_dir, sparse_dir):
        if self.params.use_glomap:
            # GLOMAP Integration
            self.log("Utilisation de GLOMAP pour la reconstruction...")
            
            cmd = [
                self.glomap_bin, 'mapper',
                '--database_path', database_path,
                '--image_path', images_dir,
                '--output_path', sparse_dir
            ]
            
            # Note: GLOMAP output structure might need verification, typically creates/uses sparse/0
            # If glomap fails due to missing binary it will be caught by run_command exception handler
            return self.run_command(cmd, "Reconstruction 3D (GLOMAP)")
            
        else:
            # Standard COLMAP Mapper
            cmd = [
                self.colmap_bin, 'mapper',
                '--database_path', database_path,
                '--image_path', images_dir,
                '--output_path', sparse_dir,
                '--Mapper.num_threads', str(self.num_threads),
                '--Mapper.min_model_size', str(self.params.min_model_size),
                '--Mapper.multiple_models', '1' if self.params.multiple_models else '0',
                '--Mapper.ba_refine_focal_length', '1' if self.params.ba_refine_focal_length else '0',
                '--Mapper.ba_refine_principal_point', '1' if self.params.ba_refine_principal_point else '0',
                '--Mapper.ba_refine_extra_params', '1' if self.params.ba_refine_extra_params else '0',
                '--Mapper.min_num_matches', str(self.params.min_num_matches),
            ]
            return self.run_command(cmd, "Reconstruction 3D (COLMAP)")

    def image_undistorter(self, images_dir: str, sparse_dir: str, output_dir: str):
        input_path = Path(sparse_dir) / "0"
        cmd = [
            self.colmap_bin, 'image_undistorter',
            '--image_path', images_dir,
            '--input_path', str(input_path),
            '--output_path', output_dir,
            '--output_type', 'COLMAP',
            '--max_image_size', str(self.params.max_image_size),
        ]
        return self.run_command(cmd, "Undistortion des images")

    def create_brush_config(self, output_dir: Path, images_dir: Path, sparse_dir: Path):
        # Determine actual paths to use (Undistorted vs Original)
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
        """Arrête le processus en cours"""
        if self._current_process and self._current_process.poll() is None:
            self.log("\nArret demande - Terminaison du processus...")
            try:
                self._current_process.terminate()
                self._current_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._current_process.kill()
                self._current_process.wait()

    @staticmethod
    def delete_project_content(target_path: Path):
        """Supprime le contenu d'un dossier de projet de manière sécurisée (Corbeille)"""
        if not target_path.exists():
            return False, "Le dossier n'existe pas"
            
        try:
            # Empty the directory by moving content to trash (except images)
            for item in target_path.iterdir():
                if item.name == "images":
                    continue
                    
                try:
                    send2trash.send2trash(str(item))
                except Exception as e:
                    print(f"Failed to trash {item}. Reason: {e}")
                    
            return True, "Contenu mis à la corbeille"
        except Exception as e:
            return False, str(e)

