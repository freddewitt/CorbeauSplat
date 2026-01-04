import os
import shutil
from PyQt6.QtCore import pyqtSignal
from app.core.engine import ColmapEngine
from app.core.brush_engine import BrushEngine
from app.gui.base_worker import BaseWorker

class ColmapWorker(BaseWorker):
    """Thread worker pour exécuter COLMAP via le moteur"""
    
    def __init__(self, params, input_path, output_path, input_type, fps):
        super().__init__()
        self.engine = ColmapEngine(
            params, input_path, output_path, input_type, fps,
            logger_callback=self.log_signal.emit,
            progress_callback=self.progress_signal.emit,
            check_cancel_callback=self.isInterruptionRequested
        )
        
    def stop(self):
        self.engine.stop()
        super().stop()
        
    def run(self):
        success, message = self.engine.run()
        self.finished_signal.emit(success, message)

class BrushWorker(BaseWorker):
    """Thread worker pour exécuter Brush"""
    
    def __init__(self, input_path, output_path, params):
        super().__init__()
        self.engine = BrushEngine()
        self.input_path = input_path
        self.output_path = output_path
        self.params = params
        
    def resolve_dataset_root(self, path):
        """
        Tente de resoudre la racine du dataset si l'utilisateur a selectionne
        un sous-dossier comme sparse/0 ou sparse.
        """
        # Normalisation
        path = os.path.normpath(path)
        
        # Cas sparse/0 -> remonter de 2 niveaux
        if path.endswith(os.path.join("sparse", "0")):
            return os.path.dirname(os.path.dirname(path))
            
        # Cas sparse -> remonter de 1 niveau
        if path.endswith("sparse"):
            return os.path.dirname(path)
            
        return path

    def stop(self):
        self.engine.stop()
        super().stop()
        
    def run(self):
        try:
            # Resolution automatique du chemin dataset
            resolved_input = self.resolve_dataset_root(self.input_path)
            
            if resolved_input != self.input_path:
                self.log_signal.emit(f"Chemin ajusté: {self.input_path} -> {resolved_input}")
            
            process = self.engine.train(
                resolved_input, 
                self.output_path, 
                iterations=self.params.get("iterations"),
                sh_degree=self.params.get("sh_degree"),
                device=self.params.get("device"),
                custom_args=self.params.get("custom_args"),
                with_viewer=self.params.get("with_viewer")
            )
            
            # Read stdout line by line
            for line in iter(process.stdout.readline, ''):
                if not self.is_running:
                    break
                if line:
                    self.log_signal.emit(line.strip())
                    
            process.stdout.close()
            return_code = process.wait()
            
            if return_code == 0:
                self.handle_ply_rename()
                self.finished_signal.emit(True, "Entrainement Brush terminé avec succès")
            else:
                self.finished_signal.emit(False, f"Erreur Brush (Code {return_code})")
                
        except Exception as e:
            self.finished_signal.emit(False, str(e))

    def handle_ply_rename(self):
        """Gère le renommage sécurisé du fichier PLY"""
        ply_name = self.params.get("ply_name")
        if not ply_name:
            return

        # Sanitization: Ensure strictly a filename, no paths
        ply_name = os.path.basename(ply_name)
        if not ply_name.endswith('.ply'):
            ply_name += '.ply'
            
        # Optimization: Look in specific likely folders first instead of full walk
        # Brush usually outputs to output_path or output_path/point_cloud/iteration_30000/
        search_paths = [
            self.output_path,
            os.path.join(self.output_path, "point_cloud", "iteration_30000"),
            os.path.join(self.output_path, "point_cloud", "iteration_7000")
        ]
        
        found_ply = None
        last_mtime = 0
        
        # Helper to check a dir
        def check_dir(directory):
            nonlocal found_ply, last_mtime
            if not os.path.exists(directory): return
            
            for file in os.listdir(directory):
                if file.endswith('.ply') and file != ply_name: # Don't overwrite if already same name
                    full_path = os.path.join(directory, file)
                    mtime = os.path.getmtime(full_path)
                    if mtime > last_mtime:
                        last_mtime = mtime
                        found_ply = full_path

        # 1. Check likely paths first
        for path in search_paths:
            check_dir(path)
            
        # 2. If nothing found, fallback to limited depth walk (e.g. max depth 3) to avoid huge trees
        if not found_ply:
            for root, dirs, files in os.walk(self.output_path):
                # Simple depth check logic could be added here if needed, but os.walk is default recursive
                # We'll just rely on the walk if direct paths check failed.
                for file in files:
                     if file.endswith('.ply'):
                        full_path = os.path.join(root, file)
                        mtime = os.path.getmtime(full_path)
                        if mtime > last_mtime:
                            last_mtime = mtime
                            found_ply = full_path

        if found_ply:
            dest_path = os.path.join(self.output_path, ply_name)
            try:
                shutil.move(found_ply, dest_path)
                self.log_signal.emit(f"Fichier PLY renommé en : {ply_name}")
            except Exception as e:
                self.log_signal.emit(f"Erreur renommage PLY: {str(e)}")
        else:
            self.log_signal.emit("Attention: Aucun fichier PLY trouvé à renommer.")

class SharpWorker(BaseWorker):
    """Thread worker pour exécuter Apple ML Sharp"""
    
    def __init__(self, input_path, output_path, params):
        super().__init__()
        # On importe ici pour eviter les cycles si besoin, ou juste par proprete
        from app.core.sharp_engine import SharpEngine
        self.engine = SharpEngine()
        self.input_path = input_path
        self.output_path = output_path
        self.params = params
        
    def stop(self):
        self.engine.stop()
        super().stop()
        
    def run(self):
        try:
            process = self.engine.predict(
                self.input_path,
                self.output_path,
                checkpoint=self.params.get("checkpoint"),
                device=self.params.get("device"),
                verbose=self.params.get("verbose")
            )
            
            # Read stdout line by line
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    if not self.is_running:
                        break
                    if line:
                        self.log_signal.emit(line.strip())
                process.stdout.close()
                
            return_code = process.wait()
            
            if return_code == 0:
                self.finished_signal.emit(True, "Prediction Sharp terminée avec succès")
            else:
                self.finished_signal.emit(False, f"Erreur Sharp (Code {return_code})")
                
        except Exception as e:
            self.finished_signal.emit(False, str(e))
