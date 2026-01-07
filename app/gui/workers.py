import os
import shutil
from PyQt6.QtCore import pyqtSignal
from app.core.engine import ColmapEngine
from app.core.brush_engine import BrushEngine
from app.gui.base_worker import BaseWorker

class ColmapWorker(BaseWorker):
    """Thread worker pour exécuter COLMAP via le moteur"""
    
    def __init__(self, params, input_path, output_path, input_type, fps, project_name="Untitled"):
        super().__init__()
        self.engine = ColmapEngine(
            params, input_path, output_path, input_type, fps, project_name,
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
            
            # Gestion de la résolution manuelle
            custom_args = self.params.get("custom_args") or ""
            max_res = self.params.get("max_resolution", 0)
            
            if max_res > 0:
                custom_args += f" --max-resolution {max_res}"
                self.log_signal.emit(f"Opération: Résolution forcée à {max_res}px")
            
            # Gestion Refine Auto (Prioritaire sur Init PLY manuel)
            refine_mode = self.params.get("refine_mode")
            # self.log_signal.emit(f"Refine Mode: {refine_mode}") # Verbose
            
            if refine_mode:
                self.log_signal.emit("Configuration Refine Auto...")
                checkpoints_dir = os.path.join(resolved_input, "checkpoints")
                
                # 1. Trouver le dernier PLY
                latest_ply = None
                last_mtime = 0
                if os.path.exists(checkpoints_dir):
                    for root, dirs, files in os.walk(checkpoints_dir):
                        for f in files:
                            if f.endswith('.ply'):
                                p = os.path.join(root, f)
                                mt = os.path.getmtime(p)
                                if mt > last_mtime:
                                    last_mtime = mt
                                    latest_ply = p
                
                if latest_ply:
                    self.log_signal.emit(f"Checkpoint trouvé: {os.path.basename(latest_ply)}")
                    
                    # 2. Créer dossier Refine
                    refine_dir = os.path.join(resolved_input, "Refine")
                    if os.path.exists(refine_dir):
                        shutil.rmtree(refine_dir) # On repart propre ? Ou on garde ? Mieux vaut clean pour être sûr de l'init
                    os.makedirs(refine_dir, exist_ok=True)
                    
                    # 3. Copier init.ply
                    dest_init = os.path.join(refine_dir, "init.ply")
                    shutil.copy2(latest_ply, dest_init)
                    self.log_signal.emit(f"Copié vers {dest_init}")
                    
                    # 4. Symlinks sparse & images
                    # Sur Windows ça peut poser souci, mais user = Mac
                    try:
                        os.symlink(os.path.join(resolved_input, "sparse"), os.path.join(refine_dir, "sparse"))
                        try:
                            os.symlink(os.path.join(resolved_input, "images"), os.path.join(refine_dir, "images"))
                        except OSError:
                            # Fallback si images est un lien ou autre
                            self.log_signal.emit("Symlink images échoué, tentative copie (plus lent)...")
                            shutil.copytree(os.path.join(resolved_input, "images"), os.path.join(refine_dir, "images"))

                        self.log_signal.emit("Symlinks créés pour sparse/ et images/")
                        
                        # 5. Rediriger l'entraînement
                        resolved_input = refine_dir
                        self.output_path = os.path.join(refine_dir, "checkpoints")
                        os.makedirs(self.output_path, exist_ok=True)
                        self.log_signal.emit(f"Dossier travail redirigé vers : {refine_dir}")
                        
                    except Exception as e:
                        self.log_signal.emit(f"Erreur création environnement Refine: {e}")
                else:
                    self.log_signal.emit("Attention: Aucun checkpoint précédent trouvé pour le Refine. Mode annulé.")

            # Fin gestion Init / Refine

            # Args Densification
            # Brush utilise iterations comme "total-steps" deja dans le moteur, mais on peut forcer les autres
            # Attention, si on passe iterations au moteur, il met --total-steps.
            # On va passer les autres en custom args.
            
            densify_args = []
            if "start_iter" in self.params: densify_args.append(f"--start-iter {self.params['start_iter']}")
            if "refine_every" in self.params: densify_args.append(f"--refine-every {self.params['refine_every']}")
            if "growth_grad_threshold" in self.params: densify_args.append(f"--growth-grad-threshold {self.params['growth_grad_threshold']}")
            if "growth_select_fraction" in self.params: densify_args.append(f"--growth-select-fraction {self.params['growth_select_fraction']}")
            if "growth_stop_iter" in self.params: densify_args.append(f"--growth-stop-iter {self.params['growth_stop_iter']}")
            if "max_splats" in self.params: densify_args.append(f"--max-splats {self.params['max_splats']}")
            
            if densify_args:
                custom_args += " " + " ".join(densify_args)

            process = self.engine.train(
                resolved_input, 
                self.output_path, 
                iterations=self.params.get("total_steps"), # Utilisation explicite de total_steps
                sh_degree=self.params.get("sh_degree"),
                device=self.params.get("device"),
                custom_args=custom_args.strip(),
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
