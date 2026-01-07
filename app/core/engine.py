import os
import sys
import subprocess
import json
import platform
from .params import ColmapParams
from .system import is_apple_silicon, get_optimal_threads, resolve_binary

class ColmapEngine:
    """Moteur d'exécution COLMAP indépendant de l'interface graphique"""
    
    def __init__(self, params, input_path, output_path, input_type, fps, project_name="Untitled", logger_callback=None, progress_callback=None, check_cancel_callback=None):
        self.params = params
        self.input_path = input_path
        self.output_path = output_path
        self.input_type = input_type
        self.fps = fps
        self.project_name = project_name
        self.is_silicon = is_apple_silicon()
        self.num_threads = get_optimal_threads()
        self._current_process = None
        self.logger = logger_callback if logger_callback else print
        self.progress = progress_callback if progress_callback else lambda x: None
        self.check_cancel = check_cancel_callback if check_cancel_callback else lambda: False
        
        # Resolve binaries
        self.ffmpeg_bin = resolve_binary('ffmpeg') or 'ffmpeg'
        self.colmap_bin = resolve_binary('colmap') or 'colmap'
        self.glomap_bin = resolve_binary('glomap') or 'glomap'
        
        if self.is_silicon:
            self.log(f"Apple Silicon detecte - {self.num_threads} threads optimises")
        self.log(f"Binaires: {self.colmap_bin}, {self.ffmpeg_bin}, {self.glomap_bin}")

    def log(self, message):
        self.logger(message)
        
    def is_cancelled(self):
        return self.check_cancel()

    def run(self):
        """Exécute le pipeline complet"""
        try:
            # Creation de la structure Projet
            # [Output] / [ProjectName] / [images, checkpoints, sparse, dense]
            project_dir = os.path.join(self.output_path, self.project_name)
            images_dir = os.path.join(project_dir, "images")
            checkpoints_dir = os.path.join(project_dir, "checkpoints")
            
            os.makedirs(project_dir, exist_ok=True)
            os.makedirs(images_dir, exist_ok=True)
            os.makedirs(checkpoints_dir, exist_ok=True)
            
            self.log(f"Preparation du projet dans : {project_dir}")
            
            # Preparation des Images (Extraction ou Copie)
            if self.input_type == "video":
                if self.is_cancelled(): return False, "Arrete par l'utilisateur"
                    
                # Extraction dans le dossier images du projet
                if not self.extract_frames_from_video(self.input_path, images_dir):
                     return False, "Echec extraction video"
            else:
                # Copie des images dans le dossier images du projet
                self.log("Copie des images sources vers le dossier de travail...")
                import shutil
                try:
                    src_files = [f for f in os.listdir(self.input_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                    for f in src_files:
                        if self.is_cancelled(): return False, "Arrete par l'utilisateur"
                        shutil.copy2(os.path.join(self.input_path, f), os.path.join(images_dir, f))
                    self.log(f"{len(src_files)} images copiees.")
                except Exception as e:
                    return False, f"Erreur copie images: {e}"
                
            # Structure de dossiers
            database_path = os.path.join(project_dir, "database.db")
            sparse_dir = os.path.join(project_dir, "sparse")
            os.makedirs(sparse_dir, exist_ok=True)
            
            self.progress(25)
            
            # 1. Feature Extraction
            if self.is_cancelled(): return False, "Arrete par l'utilisateur"
                
            if not self.feature_extraction(database_path, images_dir):
                if self.is_cancelled(): return False, "Arrete par l'utilisateur"
                return False, "Echec extraction features"
                
            self.progress(50)
            
            # 2. Feature Matching
            if self.is_cancelled(): return False, "Arrete par l'utilisateur"
                
            if not self.feature_matching(database_path):
                if self.is_cancelled(): return False, "Arrete par l'utilisateur"
                return False, "Echec matching"
                
            self.progress(75)
            
            # 3. Reconstruction
            if self.is_cancelled(): return False, "Arrete par l'utilisateur"
                
            if not self.mapper(database_path, images_dir, sparse_dir):
                if self.is_cancelled(): return False, "Arrete par l'utilisateur"
                return False, "Echec reconstruction"
                
            self.progress(90)
            
            # 4. Image Undistortion (Optionnel)
            if self.params.undistort_images:
                if self.is_cancelled(): return False, "Arrete par l'utilisateur"
                    
                dense_dir = os.path.join(project_dir, "dense")
                os.makedirs(dense_dir, exist_ok=True)
                
                if not self.image_undistorter(images_dir, sparse_dir, dense_dir):
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

    def extract_frames_from_video(self, video_path, images_dir):
        """Extraction vidéo optimisée"""
        self.log(f"\n{'='*60}\nExtraction frames\n{'='*60}")
        # images_dir est deja le dossier final
        os.makedirs(images_dir, exist_ok=True)
        
        cmd = [self.ffmpeg_bin]
        if self.is_silicon:
            cmd.extend(['-hwaccel', 'videotoolbox'])
        
        cmd.extend([
            '-i', video_path,
            '-vf', f'fps={self.fps}',
            '-qscale:v', '2',
            os.path.join(images_dir, 'frame_%04d.jpg')
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
                num_frames = len([f for f in os.listdir(images_dir) if f.endswith('.jpg')])
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
                '--SiftMatching.max_ratio', str(self.params.max_ratio),
                '--SiftMatching.max_distance', str(self.params.max_distance),
                '--SiftMatching.cross_check', '1' if self.params.cross_check else '0',
            ]
            description = "Matching Sequentiel"
        else:
            cmd = [
                self.colmap_bin, 'exhaustive_matcher',
                '--database_path', database_path,
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
                '--Mapper.min_model_size', str(self.params.min_model_size),
                '--Mapper.multiple_models', '1' if self.params.multiple_models else '0',
                '--Mapper.ba_refine_focal_length', '1' if self.params.ba_refine_focal_length else '0',
                '--Mapper.ba_refine_principal_point', '1' if self.params.ba_refine_principal_point else '0',
                '--Mapper.ba_refine_extra_params', '1' if self.params.ba_refine_extra_params else '0',
                '--Mapper.min_num_matches', str(self.params.min_num_matches),
            ]
            return self.run_command(cmd, "Reconstruction 3D (COLMAP)")

    def image_undistorter(self, images_dir, sparse_dir, output_dir):
        input_path = os.path.join(sparse_dir, "0")
        cmd = [
            self.colmap_bin, 'image_undistorter',
            '--image_path', images_dir,
            '--input_path', input_path,
            '--output_path', output_dir,
            '--output_type', 'COLMAP',
            '--max_image_size', str(self.params.max_image_size),
        ]
        return self.run_command(cmd, "Undistortion des images")

    def create_brush_config(self, output_dir, images_dir, sparse_dir):
        # Determine actual paths to use (Undistorted vs Original)
        if self.params.undistort_images:
            final_images_path = os.path.join(output_dir, "dense", "images")
            final_sparse_path = os.path.join(output_dir, "dense", "sparse")
            self.log("Utilisation des images et reconstruction non-distordues pour Brush")
        else:
            final_images_path = images_dir
            final_sparse_path = os.path.join(sparse_dir, "0")
            
        config = {
            "dataset_type": "colmap",
            "images_path": final_images_path,
            "sparse_path": final_sparse_path,
            "created_with": "CorbeauSplat macOS",
            "architecture": platform.machine(),
            "optimized_for": "Apple Silicon" if self.is_silicon else "x86_64",
            "parameters": self.params.to_dict()
        }
        config_path = os.path.join(output_dir, "brush_config.json")
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        self.log(f"Configuration Brush creee: {config_path}")
        
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
