import os
import shutil
import re
import shlex
from pathlib import Path
from PyQt6.QtCore import pyqtSignal
from app.core.engine import ColmapEngine
from app.core.brush_engine import BrushEngine
from app.gui.base_worker import BaseWorker
from app.core.extractor_360_engine import Extractor360Engine

class Extractor360Worker(BaseWorker):
    """Thread worker pour exécuter 360Extractor"""
    
    def run(self):
        self.log_signal.emit("--- Démarrage 360Extractor ---")
        if not self.engine.is_installed():
            self.finished_signal.emit(False, "360Extractor non installé.")
            return

        # Use engine to construct/run instead of manual cmd construction
        success = self.engine.run_extraction(
            self.input_path, 
            self.output_path, 
            self.params,
            progress_callback=self.progress_signal.emit,
            log_callback=self.log_signal.emit
        )
        
        if success:
            self.finished_signal.emit(True, "Extraction terminée avec succès.")
        else:
            self.finished_signal.emit(False, "Erreur lors de l'extraction.")

    def parse_line(self, line):
        """Extraction naïve de la progression [XX%]"""
        if "%]" in line and "[" in line:
            try:
                part = line.split("[")[1].split("%]")[0].strip()
                self.progress_signal.emit(int(part))
            except: pass

class ColmapWorker(BaseWorker):
    """Thread worker pour exécuter COLMAP via le moteur"""
    
    def __init__(self, params, input_path, output_path, input_type, fps, project_name="Untitled", upscale_params=None, extractor_360_params=None):
        super().__init__()
        self.upscale_params = upscale_params
        self.extractor_360_params = extractor_360_params
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
        # 1. Check 360 Extractor
        if self.extractor_360_params and self.extractor_360_params.get("enabled", False):
            from app.core.extractor_360_engine import Extractor360Engine
            ext_360 = Extractor360Engine()
            
            if not ext_360.is_installed():
                self.log_signal.emit("ERREUR: 360 Extractor activé mais non installé.")
                self.finished_signal.emit(False, "Dépendances 360 manquantes")
                return

            self.log_signal.emit("--- Démarrage 360 Extractor (Pré-traitement) ---")
            
            # Output images to project/images
            images_dir = self.engine.project_path / "images"
            images_dir.mkdir(parents=True, exist_ok=True)
            
            # Run extraction
            success = ext_360.run_extraction(
                self.engine.input_path, # Video path
                images_dir, # Output folder
                self.extractor_360_params,
                progress_callback=self.progress_signal.emit,
                log_callback=self.log_signal.emit
            )
            
            if not success:
                self.finished_signal.emit(False, "Echec de l'extraction 360.")
                return
                
            self.log_signal.emit("Extraction 360 terminée. Passage à COLMAP...")
            
            self.engine.input_type = "images" 
            self.engine.input_path = images_dir
            
            # Need to update image_path internal in engine if it was already resolved?
            # ColmapEngine init resolves paths.
            # Let's verify ColmapEngine internals later, but for now assuming property update works 
            # or we re-instantiate logic? 
            # Actually ColmapEngine might have already set internal variables. 
            # Let's hope modifying input_path matches. 
            # Update: ColmapEngine.run() uses self.input_path. So it's fine.

        # 2. Check Upscale 
        if self.upscale_params and self.upscale_params.get("active", False):
            # ... (Existing logic or placeholder)
            self.engine.upscale_config = self.upscale_params # Inject manually for now
        
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
        
    def resolve_dataset_root(self, path: Path) -> Path:
        """
        Tente de resoudre la racine du dataset si l'utilisateur a selectionne
        un sous-dossier comme sparse/0 ou sparse.
        """
        # Cas sparse/0 -> remonter de 2 niveaux
        if path.name == "0" and path.parent.name == "sparse":
            return path.parent.parent
            
        # Cas sparse -> remonter de 1 niveau
        if path.name == "sparse":
            return path.parent
            
        return path

    def stop(self):
        self.engine.stop()
        super().stop()
        
    def run(self):
        try:
            self.log_signal.emit(f"Initialisation BrushWorker...")
            self.log_signal.emit(f"Input: {self.input_path}")
            self.log_signal.emit(f"Output: {self.output_path}")

            # Resolution automatique du chemin dataset
            resolved_input = self.resolve_dataset_root(Path(self.input_path))
            
            if str(resolved_input) != str(self.input_path):
                self.log_signal.emit(f"Chemin ajusté: {self.input_path} -> {resolved_input}")
            
            if not resolved_input.exists():
                self.finished_signal.emit(False, f"Le dossier dataset n'existe pas: {resolved_input}")
                return

            # Gestion de la résolution manuelle
            custom_args = self.params.get("custom_args") or ""
            max_res = self.params.get("max_resolution", 0)
            
            if max_res > 0:
                custom_args += f" --max-resolution {max_res}"
                self.log_signal.emit(f"Opération: Résolution forcée à {max_res}px")
            
            # Gestion Refine Auto (Prioritaire sur Init PLY manuel)
            refine_mode = self.params.get("refine_mode")
            
            if refine_mode:
                self.log_signal.emit("Mode Raffinement (Refine) activé...")
                checkpoints_dir = resolved_input / "checkpoints"
                
                # 1. Trouver le dernier PLY
                latest_ply = None
                last_mtime = 0
                if checkpoints_dir.exists():
                    self.log_signal.emit(f"Recherche de checkpoints dans {checkpoints_dir}...")
                    for p in checkpoints_dir.rglob("*.ply"):
                        mt = p.stat().st_mtime
                        if mt > last_mtime:
                            last_mtime = mt
                            latest_ply = p
                
                if latest_ply:
                    self.log_signal.emit(f"Checkpoint trouvé: {latest_ply.name}")
                    
                    # 2. Créer dossier Refine
                    refine_dir = resolved_input / "Refine"
                    self.log_signal.emit(f"Préparation du dossier de raffinement: {refine_dir}")
                    
                    # Safety check: Ensure refine_dir is inside resolved_input
                    try:
                        if refine_dir.exists():
                            shutil.rmtree(refine_dir) 
                        refine_dir.mkdir(parents=True, exist_ok=True)
                    except Exception as e:
                        self.log_signal.emit(f"ERREUR lors de la préparation du dossier Refine: {e}")
                        self.finished_signal.emit(False, f"Erreur dossier Refine: {e}")
                        return
                    
                    # 3. Copier init.ply
                    dest_init = refine_dir / "init.ply"
                    try:
                        shutil.copy2(latest_ply, dest_init)
                        self.log_signal.emit(f"Copié {latest_ply.name} vers {dest_init}")
                    except Exception as e:
                        self.log_signal.emit(f"ERREUR lors de la copie de init.ply: {e}")
                        self.finished_signal.emit(False, f"Erreur copie init.ply: {e}")
                        return
                    
                    # 4. Symlinks sparse & images
                    try:
                        self.log_signal.emit("Création des liens symboliques pour sparse et images...")
                        os.symlink(resolved_input / "sparse", refine_dir / "sparse")
                        try:
                            os.symlink(resolved_input / "images", refine_dir / "images")
                        except OSError as e:
                            self.log_signal.emit(f"Symlink images échoué ({e}), tentative copie (plus lent)...")
                            shutil.copytree(resolved_input / "images", refine_dir / "images")

                        self.log_signal.emit("Liens symboliques/copies terminés.")
                        
                        # 5. Rediriger l'entraînement
                        resolved_input = refine_dir
                        self.output_path = refine_dir / "checkpoints"
                        self.output_path.mkdir(parents=True, exist_ok=True)
                        self.log_signal.emit(f"Dossier de travail redirigé vers: {refine_dir}")
                        
                    except Exception as e:
                        self.log_signal.emit(f"Erreur fatale lors de la création de l'environnement Refine: {e}")
                        self.finished_signal.emit(False, f"Erreur env Refine: {e}")
                        return
                        
                    # Auto-detect start_iter from filename or default to 30000
                    if self.params.get("start_iter", 0) == 0:
                        detected_iter = 30000
                        match = re.search(r"iteration_(\d+)", latest_ply.name)
                        if match:
                            detected_iter = int(match.group(1))
                        
                        self.params["start_iter"] = detected_iter
                        self.log_signal.emit(f"Refine: Start Iteration réglé sur {detected_iter}")
                else:
                    self.log_signal.emit("AVERTISSEMENT: Mode Refine activé mais aucun checkpoint (.ply) trouvé. Lancement mode normal.")

            # Fin gestion Init / Refine

            # Args Densification
            densify_args = []
            if "start_iter" in self.params: densify_args.append(f"--start-iter {self.params['start_iter']}")
            if "refine_every" in self.params: densify_args.append(f"--refine-every {self.params['refine_every']}")
            if "growth_grad_threshold" in self.params: densify_args.append(f"--growth-grad-threshold {self.params['growth_grad_threshold']}")
            if "growth_select_fraction" in self.params: densify_args.append(f"--growth-select-fraction {self.params['growth_select_fraction']}")
            if "growth_stop_iter" in self.params: densify_args.append(f"--growth-stop-iter {self.params['growth_stop_iter']}")
            if "max_splats" in self.params: densify_args.append(f"--max-splats {self.params['max_splats']}")
            
            # Checkpoint Interval (Mapped to --eval-every as per Brush CLI)
            ckpt_interval = self.params.get("checkpoint_interval", 7000)
            if ckpt_interval > 0:
                densify_args.append(f"--eval-every {ckpt_interval}")
            
            if densify_args:
                custom_args += " " + " ".join(densify_args)

            # Construct CMD
            self.log_signal.emit("Lancement de la commande Brush...")
            # Use refactored train method
            process = self.engine.train(resolved_input, self.output_path, self.params)
            
            # Capture output from process
            success = True
            if process:
                for line in process.stdout:
                    if not self.is_running or self.isInterruptionRequested():
                        self.log_signal.emit("Processus arrêté par l'utilisateur.")
                        self.engine.stop()
                        success = False
                        break
                    
                    clean_line = line.strip()
                    if clean_line:
                        self.log_signal.emit(clean_line)
                
                process.wait()
                if process.returncode != 0:
                    success = False
            else:
                success = False
            
            if success:
                self.handle_ply_rename()
                self.finished_signal.emit(True, "Entrainement Brush terminé avec succès")
            else:
                self.finished_signal.emit(False, "Brush a retourné une erreur (voir logs ci-dessus).")
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.log_signal.emit(f"EXCEPTION dans BrushWorker: {e}\n{error_details}")
            self.finished_signal.emit(False, f"Exception: {e}")

    def handle_ply_rename(self):
        """Gère le renommage sécurisé du fichier PLY"""
        ply_name = self.params.get("ply_name")
        if not ply_name:
            return

        # Sanitization: Ensure strictly a filename, no paths
        ply_name = Path(ply_name).name
        if not ply_name.endswith('.ply'):
            ply_name += '.ply'
            
        output_path = Path(self.output_path)
            
        # Optimization: Look in specific likely folders first
        search_paths = [
            output_path,
            output_path / "point_cloud" / "iteration_30000",
            output_path / "point_cloud" / "iteration_7000"
        ]
        
        found_ply = None
        last_mtime = 0
        
        # Helper to check a dir
        def check_dir(directory: Path):
            nonlocal found_ply, last_mtime
            if not directory.exists(): return
            
            for p in directory.iterdir():
                if p.is_file() and p.suffix == '.ply' and p.name != ply_name:
                    mt = p.stat().st_mtime
                    if mt > last_mtime:
                        last_mtime = mt
                        found_ply = p

        # 1. Check likely paths first
        for path in search_paths:
            check_dir(path)
            
        # 2. If nothing found, fallback to walk
        if not found_ply:
            for p in output_path.rglob("*.ply"):
                if p.name != ply_name:
                    mt = p.stat().st_mtime
                    if mt > last_mtime:
                        last_mtime = mt
                        found_ply = p

        if found_ply:
            dest_path = output_path / ply_name
            try:
                shutil.move(str(found_ply), str(dest_path))
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
            # Handle Upscale
            if self.params.get("upscale", False):
                from app.core.upscale_engine import UpscaleEngine
                upscaler = UpscaleEngine(logger_callback=self.log_signal.emit)
                if upscaler.is_installed():
                    self.log_signal.emit("--- Upscale Image ---")
                    input_path = Path(self.input_path)
                    output_path = Path(self.output_path)
                    if input_path.is_file():
                        temp_dir = output_path / "temp_upscale"
                        temp_dir.mkdir(parents=True, exist_ok=True)
                        upscaled_path = temp_dir / input_path.name
                        model = upscaler.load_model()
                        if model and upscaler.upscale_image(input_path, upscaled_path, model):
                            self.input_path = str(upscaled_path)
                            self.log_signal.emit("Upscale terminé. Lancement Sharp...")
                        else:
                            self.log_signal.emit("Echec Upscale. Utilisation image originale.")
                    else:
                        self.log_signal.emit("Upscale de dossier pour Sharp non supporté dans cette version simple (TODO).")
                else:
                    self.log_signal.emit("Erreur: Upscale demandé mais non installé.")
            
            # Use refactored predict method
            process = self.engine.predict(self.input_path, self.output_path, self.params)
            
            success = True
            if process:
                for line in process.stdout:
                    if not self.is_running or self.isInterruptionRequested():
                        self.log_signal.emit("Processus arrêté par l'utilisateur.")
                        self.engine.stop()
                        success = False
                        break
                    
                    clean_line = line.strip()
                    if clean_line:
                        self.log_signal.emit(clean_line)
                
                process.wait()
                if process.returncode != 0:
                    success = False
            else:
                success = False
            self.finished_signal.emit(success, "Prediction Sharp terminée avec succès" if success else "Erreur Sharp.")
        except Exception as e:
            self.finished_signal.emit(False, str(e))



# ---------------------------------------------------------------------
# 4DGS WORKER
# ---------------------------------------------------------------------
from app.core.four_dgs_engine import FourDGSEngine

class FourDGSWorker(BaseWorker):
    def __init__(self, videos_dir, output_dir, fps=5):
        super().__init__()
        self.videos_dir = videos_dir
        self.output_dir = output_dir
        self.fps = fps
        self.engine = None

    def run(self):
        self.log_signal.emit("--- Démarrage 4DGS ---")
        self.engine = FourDGSEngine(logger_callback=self.log_signal.emit)
        
        # 4DGS process is more complex, but we can still use run_subprocess for its internal steps if needed.
        # For now, keep it calling engine.process_dataset but ensure engine doesn't block if we can.
        # Actually FourDGSEngine.process_dataset likely runs subprocesses.
        
        try:
            if self.videos_dir:
                success = self.engine.process_dataset(self.videos_dir, self.output_dir, self.fps)
            else:
                # COLMAP ONLY MODE
                success = self.engine.run_colmap(self.output_dir)
                
            self.finished_signal.emit(success, "Dataset 4DGS créé avec succès." if success else "Échec du traitement 4DGS.")
        except Exception as e:
            self.finished_signal.emit(False, str(e))

    def stop(self):
        self._is_running = False
        if self.engine:
            self.engine.stop()
