import os
import subprocess
import concurrent.futures
import shutil
from pathlib import Path
from .base_engine import BaseEngine
from .system import resolve_binary, is_apple_silicon, get_optimal_threads

class FourDGSEngine(BaseEngine):
    """
    Moteur pour la préparation de datasets 4DGS (Video -> COLMAP -> Nerfstudio).
    """
    def __init__(self, logger_callback=None):
        super().__init__("4DGS", logger_callback)
        
        # Resolve binaries
        self.ffmpeg = resolve_binary("ffmpeg") or "ffmpeg"
        self.colmap = resolve_binary("colmap") or "colmap" 
        
    def log(self, message):
        if self.logger:
            self.logger(message)

    def stop(self):
        self.stop_requested = True

    def check_nerfstudio(self):
        """Vérifie si ns-process-data est disponible"""
        # ns-process-data est souvent un script python/entrypoint
        return shutil.which("ns-process-data") is not None

    def extract_frames(self, video_path, output_dir, fps=5):
        """Extrait les frames d'une vidéo avec ffmpeg"""
        if self.stop_requested: return False
        
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
        
        try:
            # Videotoolbox sur mac si possible ? 
            # ffmpeg gestion auto souvent ok, mais on peut tenter acceleration
            # Pour l'extraction jpg, le CPU est souvent limitant vs decode.
            # On reste simple pour la compatibilité.
            
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError as e:
            self.log(f"Erreur extraction {video_path}: {e}")
            return False

    def run_colmap(self, dataset_root):
        """Lance le pipeline COLMAP : Feature Extractor -> Matcher -> Mapper"""
        if self.stop_requested: return False
        
        root = Path(dataset_root)
        db_path = root / "database.db"
        images_path = root / "images"
        sparse_path = root / "sparse"
        sparse_path.mkdir(parents=True, exist_ok=True)

        # 1. Feature Extraction
        self.log("--- COLMAP: Feature Extraction ---")
        cmd_extract = [
            self.colmap, "feature_extractor",
            "--database_path", str(db_path),
            "--image_path", str(images_path),
            "--ImageReader.camera_model", "OPENCV",
            "--ImageReader.single_camera", "1" 
        ]
        
        if self._run_cmd(cmd_extract) != 0: return False
        
        # 2. Sequential Matching (Souvent mieux pour vidéo ?) 
        # Ou Exhaustive si peu de cams ?
        # Pour 4DGS, on a souvent des caméras fixes qui filment une scène qui bouge.
        # Exhaustive est plus sûr si < 50-100 images. Mais ici on a des milliers de frames ?
        # Non, on traite les CAMERAS.
        # En 4DGS "Nerfstudio format", on a besoin des poses des caméras.
        # On extrait souvent la première frame de chaque vidéo pour caler la géométrie, ou on utilise tout ?
        # Pour faire simple : Exhaustive Matcher est robuste.
        
        self.log("--- COLMAP: Feature Matching ---")
        cmd_match = [
            self.colmap, "exhaustive_matcher",
            "--database_path", str(db_path),
        ]

        if self._run_cmd(cmd_match) != 0: return False
        
        # 3. Mapper
        self.log("--- COLMAP: Mapper (Sparse Reconstruction) ---")
        cmd_mapper = [
            self.colmap, "mapper",
            "--database_path", str(db_path),
            "--image_path", str(images_path),
            "--output_path", str(sparse_path)
        ]
        
        # Threads
        threads = str(get_optimal_threads())
        cmd_mapper.append(f"--Mapper.num_threads={threads}")

        if self._run_cmd(cmd_mapper) != 0: return False
        
        return True

    def process_dataset(self, videos_dir, output_dir, fps=5):
        """
        Orchestre tout le processus :
        1. Scan videos
        2. Extract frames -> output/images/cam_xx
        3. Colmap (si demandé, ou ns-process-data le fait ?)
        
        NOTE: ns-process-data video fait tout (ffmpeg + colmap).
        Mais ici on a du MULTI-VIDEO (Multi-view).
        ns-process-data supporte-t-il le multi-video input ?
        
        Approche CorbeauSplat : On prépare les données 'images' et on laisse Colmap faire les poses,
        puis on formate.
        
        Pour simplifier : On va extraire les images nous-mêmes pour avoir le contrôle,
        puis lancer COLMAP.
        """
        
        self.log(f"Scan du dossier : {videos_dir}")
        supported_ext = (".mp4", ".mov", ".avi", ".mkv")
        videos_path = Path(videos_dir)
        videos = sorted([f for f in videos_path.iterdir() if f.suffix.lower() in supported_ext])
        
        if not videos:
            self.log("Aucune vidéo trouvée.")
            return False
            
        self.log(f"Trouvé {len(videos)} vidéos. Début extraction...")
        
        images_root = Path(output_dir) / "images"
        images_root.mkdir(parents=True, exist_ok=True)
        
        # 1. Extraction
        for idx, vid_path in enumerate(videos):
            if self.stop_requested: return False
            cam_name = f"cam_{idx:02d}" # cam_00, cam_01...
            cam_dir = images_root / cam_name
            
            self.log(f"Extraction {vid_path.name} -> {cam_name} ({fps} fps)...")
            if not self.extract_frames(vid_path, cam_dir, fps):
                return False
                
        self.log("Extraction terminée.")
        
        # 2. COLMAP
        # Pour du 4DGS multi-view, on veut les poses des caméras.
        # On peut lancer COLMAP sur TOUTES les images (très lourd) ou juste sur un subset (ex: frame 0 de chaque cam) pour fixer les poses ?
        # Pour l'instant, faisons simple : COLMAP sur tout le dossier images (recursive ?)
        # Colmap ne gère pas recursive par défaut sans config spécifique.
        # Alternative : ns-process-data gère ça très bien.
        
        # Si nerfstudio est là, utilisons ns-process-data images
        if self.check_nerfstudio():
            self.log("ns-process-data détecté. Lancement du processing Nerfstudio...")
            
            # ns-process-data images --data output_dir/images --output-dir output_dir
            cmd_ns = [
                "ns-process-data", "images",
                "--data", str(images_root),
                "--output-dir", str(output_dir),
                "--verbose"
            ]
            
            # Options pour aider colmap
            # Ajouter --skip-colmap si on voulait le faire nous meme, mais ns le fait bien.
            # On va laisser ns faire colmap.
            
            if self._run_cmd(cmd_ns) != 0:
                self.log("Echec ns-process-data.")
                return False
            
            return True
        else:
            self.log("Nerfstudio non trouvé. Lancement mode dégradé (COLMAP manuel uniquement).")
            # Fallback : on run colmap nous même, mais on n'aura pas le transforms.json
            return self.run_colmap(output_dir)

    def _run_cmd(self, cmd):
        if self.stop_requested: return -1
        self.log(f"Exec: {' '.join(map(str, cmd))}")
        try:
            env = os.environ.copy()
            if is_apple_silicon():
                threads = str(get_optimal_threads())
                env["OMP_NUM_THREADS"] = threads
                env["VECLIB_MAXIMUM_THREADS"] = threads
                env["OPENBLAS_NUM_THREADS"] = threads
                
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True,
                env=env
            )
            
            while True:
                if self.stop_requested:
                    process.terminate()
                    return -1
                
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    self.log(line.strip())
                    
            return process.poll()
        except Exception as e:
            self.log(f"Exception: {e}")
            return -1
