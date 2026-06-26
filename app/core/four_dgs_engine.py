import os
import subprocess
import shutil
import sys
from pathlib import Path
from .base_engine import BaseEngine
from .system import resolve_binary, has_cuda, get_optimal_threads, resolve_project_root

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
        
    def check_nerfstudio(self):
        """Vérifie si ns-process-data est disponible dans le venv dédié"""
        ns_path = _get_ns_process_data_path()
        return ns_path.exists()

    def extract_frames(self, video_path, output_dir, fps=5):
        """Extrait les frames d'une vidéo avec ffmpeg"""
        if self.stop_requested: return False

        fps = max(1, int(fps))
        out_p = Path(output_dir)
        out_p.mkdir(parents=True, exist_ok=True)

        cmd = [self.ffmpeg]
        if has_cuda():
            cmd.extend(["-hwaccel", "cuda"])

        cmd.extend([
            "-i", str(video_path),
            "-vf", f"fps={fps}",
            "-q:v", "2", # Haute qualité jpeg
            str(out_p / "%05d.jpg")
        ])
        
        # Template Method : Délégation à _execute_command centralisé
        return self._execute_command(cmd) == 0

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
        self.status("Extraction des features (COLMAP)...")
        cmd_extract = [
            self.colmap, "feature_extractor",
            "--database_path", str(db_path),
            "--image_path", str(images_path),
            "--ImageReader.camera_model", "OPENCV",
            "--ImageReader.single_camera", "1" 
        ]
        
        if self._execute_command(cmd_extract) != 0: return False
        
        self.log("--- COLMAP: Feature Matching ---")
        self.status("Matching des features...")
        cmd_match = [
            self.colmap, "exhaustive_matcher",
            "--database_path", str(db_path),
        ]

        if self._execute_command(cmd_match) != 0: return False
        
        # 3. Mapper
        self.log("--- COLMAP: Mapper (Sparse Reconstruction) ---")
        self.status("Reconstruction 3D (Mapper)...")
        cmd_mapper = [
            self.colmap, "mapper",
            "--database_path", str(db_path),
            "--image_path", str(images_path),
            "--output_path", str(sparse_path)
        ]
        
        threads = str(get_optimal_threads())
        cmd_mapper.append(f"--Mapper.num_threads={threads}")

        if self._execute_command(cmd_mapper) != 0: return False
        
        return True

    def process_dataset(self, videos_dir, output_dir, fps=5):
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
            cam_name = f"cam_{idx:02d}"
            cam_dir = images_root / cam_name
            
            self.log(f"Extraction {vid_path.name} -> {cam_name} ({fps} fps)...")
            self.status(f"Extraction des frames ({vid_path.name})...")
            if not self.extract_frames(vid_path, cam_dir, fps):
                return False
                
        self.log("Extraction terminée.")
        
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
            return self.run_colmap(output_dir)
