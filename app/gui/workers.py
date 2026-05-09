import os
import shutil
import re
import subprocess
import time
import traceback
from pathlib import Path
from app.core.engine import ColmapEngine
from app.core.brush_engine import BrushEngine
from app.core.i18n import tr
from app.gui.base_worker import BaseWorker
from app.core.extractor_360_engine import Extractor360Engine

class Extractor360Worker(BaseWorker):
    """Thread worker pour exécuter 360Extractor"""

    def __init__(self, input_path, output_path, params, engine=None):
        super().__init__()
        # DIP : Injection
        self.engine = engine or Extractor360Engine(logger_callback=self.log_signal.emit)
        self.input_path = input_path
        self.output_path = output_path
        self.params = params

    def stop(self):
        self.engine.stop()
        super().stop()

    def run(self):
        self.log_signal.emit(tr("status_360_start", "--- Démarrage 360Extractor ---"))
        if not self.engine.is_installed():
            self.finished_signal.emit(False, tr("err_360_not_installed", "360Extractor non installé."))
            return

        # Use engine to construct/run instead of manual cmd construction
        success = self.engine.run_extraction(
            self.input_path, 
            self.output_path, 
            self.params,
            progress_callback=self.progress_signal.emit,
            log_callback=self.log_signal.emit,
            check_cancel_callback=self.isInterruptionRequested
        )
        
        if success:
            self.finished_signal.emit(True, tr("status_360_done", "Extraction terminée avec succès."))
        else:
            self.finished_signal.emit(False, tr("err_360_failed", "Erreur lors de l'extraction."))

    def parse_line(self, line):
        """Extraction naïve de la progression [XX%]"""
        if "%]" in line and "[" in line:
            try:
                part = line.split("[")[1].split("%]")[0].strip()
                self.progress_signal.emit(int(part))
            except (ValueError, IndexError):
                pass

class ColmapWorker(BaseWorker):
    """Thread worker pour exécuter COLMAP via le moteur"""
    
    def __init__(self, params, input_path, output_path, input_type, fps, project_name="Untitled", upscale_params=None, extractor_360_params=None, engine=None):
        super().__init__()
        self.upscale_params = upscale_params
        self.extractor_360_params = extractor_360_params
        self.extractor_engine = None
        # DIP : Injection
        self.engine = engine or ColmapEngine(
            params, input_path, output_path, input_type, fps, project_name,
            logger_callback=self.log_signal.emit,
            progress_callback=self.progress_signal.emit,
            status_callback=self.status_signal.emit,
            check_cancel_callback=self.isInterruptionRequested
        )
        
    def stop(self):
        if self.extractor_engine:
            self.extractor_engine.stop()
        self.engine.stop()
        super().stop()
        
    def run(self):
        # 1. Check 360 Extractor
        if self.extractor_360_params and self.extractor_360_params.get("enabled", False):
            from app.core.extractor_360_engine import Extractor360Engine
            self.extractor_engine = Extractor360Engine()
            
            if not self.extractor_engine.is_installed():
                self.log_signal.emit(tr("err_360_not_installed_colmap", "ERREUR: 360 Extractor activé mais non installé."))
                self.finished_signal.emit(False, tr("err_360_missing", "Dépendances 360 manquantes"))
                return

            self.log_signal.emit(tr("status_360_pre", "--- Démarrage 360 Extractor (Pré-traitement) ---"))
            
            # Output images to project/images
            images_dir = self.engine.project_path / "images"
            images_dir.mkdir(parents=True, exist_ok=True)
            
            # Run extraction
            success = self.extractor_engine.run_extraction(
                self.engine.input_path, # Video path
                images_dir, # Output folder
                self.extractor_360_params,
                progress_callback=self.progress_signal.emit,
                log_callback=self.log_signal.emit,
                check_cancel_callback=self.isInterruptionRequested
            )
            
            if not success:
                self.finished_signal.emit(False, tr("err_360_failed", "Echec de l'extraction 360."))
                return
                
            self.log_signal.emit(tr("status_360_colmap", "Extraction 360 terminée. Passage à COLMAP..."))
            
            self.engine = ColmapEngine(
                self.engine.params, images_dir, self.engine.output_path, "images",
                self.engine.fps, self.engine.project_name,
                logger_callback=self.log_signal.emit,
                progress_callback=self.progress_signal.emit,
                status_callback=self.status_signal.emit,
                check_cancel_callback=self.isInterruptionRequested
            )

        # 2. Check Upscale 
        if self.upscale_params and self.upscale_params.get("active", False):
            self.engine.upscale_config = self.upscale_params
            self.log_signal.emit(tr("status_upscale_colmap", "--- Upscale activé pour COLMAP ---"))
        
        success, message = self.engine.run()
        self.finished_signal.emit(success, message)

class BrushWorker(BaseWorker):
    """Thread worker pour exécuter Brush"""

    def __init__(self, input_path, output_path, params, engine=None, project_name=""):
        super().__init__()
        # DIP : Injection
        self.engine = engine or BrushEngine(logger_callback=self.log_signal.emit)
        self.input_path = input_path
        self.output_path = output_path
        self.params = params
        self.project_name = project_name
        
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
                    for ply_path in checkpoints_dir.rglob("*.ply"):
                        mt = ply_path.stat().st_mtime
                        if mt > last_mtime:
                            last_mtime = mt
                            latest_ply = ply_path
                
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
                        
                    if self.params.get("start_iter", 0) == 0:
                        detected_iter = self.params.get("total_steps", 30000)
                        match = re.search(r"iteration_(\d+)", latest_ply.name)
                        if match:
                            detected_iter = int(match.group(1))
                        
                        self.params["start_iter"] = detected_iter
                        self.log_signal.emit(f"Refine: Start Iteration réglé sur {detected_iter}")
                else:
                    self.log_signal.emit("AVERTISSEMENT: Mode Refine activé mais aucun checkpoint (.ply) trouvé. Lancement mode normal.")

            # Fin gestion Init / Refine

            # Renommer les checkpoints existants avant l'archivage ou l'entraînement
            if self.project_name:
                self._rename_checkpoints_with_project_name()

            # Mode "new" : s'assurer que Brush parte d'un dossier vide
            # Brush auto-reprend depuis les checkpoints existants → on les archive
            if not refine_mode:
                output_dir = Path(self.output_path)
                has_checkpoints = output_dir.exists() and any(output_dir.rglob("*.ply"))
                if has_checkpoints:
                    backup_name = f"checkpoints_backup_{int(time.time())}"
                    backup_dir = output_dir.parent / backup_name
                    shutil.move(str(output_dir), str(backup_dir))
                    output_dir.mkdir(parents=True, exist_ok=True)
                    self.output_path = output_dir
                    self.log_signal.emit(f"Nouveau training : anciens checkpoints archivés dans '{backup_name}'")

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
                
            self.params['custom_args'] = custom_args.strip()

            # Renommer les checkpoints existants avant l'entraînement
            if self.project_name:
                self._rename_checkpoints_with_project_name()

            # Construct CMD
            self.log_signal.emit("Lancement de la commande Brush...")
            # Use refactored train method (Template Method)
            returncode = self.engine.train(resolved_input, self.output_path, self.params)
            
            # Delegate handling to Template Method return logic
            success = (returncode == 0)
            
            if success:
                self.handle_ply_rename()
                if self.project_name:
                    self._rename_checkpoints_with_project_name()
                self.finished_signal.emit(True, "Entrainement Brush terminé avec succès")
            else:
                self.finished_signal.emit(False, "Brush a retourné une erreur (voir logs ci-dessus).")
                
        except Exception as e:
            self.log_signal.emit(f"EXCEPTION dans BrushWorker: {e}\n{traceback.format_exc()}")
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
            
        last_iter = self.params.get("total_steps", 30000)
        search_paths = [
            output_path,
            output_path / "point_cloud" / f"iteration_{last_iter}",
            output_path / "point_cloud" / f"iteration_{last_iter // 2}",
        ]
        
        found_ply = None
        last_mtime = 0
        
        # Helper to check a dir
        def check_dir(directory: Path):
            nonlocal found_ply, last_mtime
            if not directory.exists(): return
            
            for file_path in directory.iterdir():
                if file_path.is_file() and file_path.suffix == '.ply' and file_path.name != ply_name:
                    mt = file_path.stat().st_mtime
                    if mt > last_mtime:
                        last_mtime = mt
                        found_ply = file_path

        # 1. Check likely paths first
        for path in search_paths:
            check_dir(path)
            
        # 2. If nothing found, fallback to walk
        if not found_ply:
            for ply_file_path in output_path.rglob("*.ply"):
                if ply_file_path.name != ply_name:
                    mt = ply_file_path.stat().st_mtime
                    if mt > last_mtime:
                        last_mtime = mt
                        found_ply = ply_file_path

        if found_ply:
            dest_path = output_path / ply_name
            try:
                shutil.move(str(found_ply), str(dest_path))
                self.log_signal.emit(f"Fichier PLY renommé en : {ply_name}")
            except Exception as e:
                self.log_signal.emit(f"Erreur renommage PLY: {str(e)}")
        else:
            self.log_signal.emit("Attention: Aucun fichier PLY trouvé à renommer.")

    def _rename_checkpoints_with_project_name(self):
        """Renomme tous les PLY de checkpoints pour inclure le nom du projet."""
        prefix = f"{self.project_name}_"
        output_path = Path(self.output_path)
        renamed = 0
        for ply_path in output_path.rglob("*.ply"):
            if not ply_path.name.startswith(prefix):
                new_name = f"{prefix}{ply_path.name}"
                dest = ply_path.parent / new_name
                try:
                    ply_path.rename(dest)
                    renamed += 1
                except Exception as e:
                    self.log_signal.emit(f"Erreur renommage {ply_path.name}: {e}")
        if renamed:
            self.log_signal.emit(f"Checkpoints renommés avec le préfixe '{prefix}' ({renamed} fichiers)")

class SharpWorker(BaseWorker):
    """Thread worker pour exécuter Apple ML Sharp"""
    
    def __init__(self, input_path, output_path, params, engine=None):
        super().__init__()
        # On importe ici pour eviter les cycles si besoin, ou juste par proprete
        from app.core.sharp_engine import SharpEngine
        # DIP : Injection
        self.engine = engine or SharpEngine(logger_callback=self.log_signal.emit)
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
                from app.upscayl_manager import run_upscayl, find_binary
                if find_binary():
                    self.log_signal.emit(tr("status_upscaling", "--- Upscale Image ---"))
                    input_path = Path(self.input_path)
                    output_path = Path(self.output_path)
                    if input_path.is_file():
                        temp_dir = output_path / "temp_upscale"
                        temp_dir.mkdir(parents=True, exist_ok=True)
                        fmt = self.params.get("format", "png")
                        model_id = self.params.get("model_id") or ""
                        if not model_id:
                            from app.upscayl_models import get_downloaded_models
                            from app.upscayl_manager import get_models_dir
                            _dl = get_downloaded_models(get_models_dir())
                            model_id = _dl[0].id if _dl else ""
                        if model_id:
                            # upscayl-bin operates on folders; use a temp input folder
                            tmp_in = temp_dir / "_in"
                            tmp_in.mkdir(exist_ok=True)
                            shutil.copy2(input_path, tmp_in / input_path.name)
                            upscale_params = {
                                "model_id":    model_id,
                                "scale":       self.params.get("scale", 4),
                                "format":      fmt,
                                "tile":        self.params.get("tile", 0),
                                "tta":         self.params.get("tta", False),
                                "compression": self.params.get("compression", 0),
                            }
                            success = [False]
                            run_upscayl(str(tmp_in), str(temp_dir), upscale_params,
                                        log_callback=self.log_signal.emit,
                                        done_callback=lambda ok: success.__setitem__(0, ok),
                                        cancel_check=self.isInterruptionRequested)
                            upscaled_path = temp_dir / (input_path.stem + "." + fmt)
                            if success[0] and upscaled_path.exists():
                                self.input_path = str(upscaled_path)
                                self.log_signal.emit(tr("status_upscale_done", "Upscale done. Launching Sharp..."))
                            else:
                                self.log_signal.emit(tr("err_upscale_failed", "Upscale failed. Using original image."))
                        else:
                            self.log_signal.emit("⚠ Upscale activé mais aucun modèle disponible — ignoré.")
                    else:
                        self.log_signal.emit(tr("err_upscale_folder", "Folder upscale not supported in Sharp mode."))
                else:
                    self.log_signal.emit(tr("err_upscale_missing", "Error: Upscale requested but upscayl-bin not found."))
            
            # Use refactored predict method
            self.status_signal.emit(tr("status_sharp", "Amélioration avec ML Sharp..."))
            
            # Délégation à la Template Method
            returncode = self.engine.predict(self.input_path, self.output_path, self.params)
            success = (returncode == 0)
            
            self.finished_signal.emit(success, "Prédiction Sharp terminée." if success else "Sharp a retourné une erreur (voir logs).")
        except Exception as e:
            self.finished_signal.emit(False, str(e))

class SharpVideoWorker(BaseWorker):
    """Thread worker for executing Apple ML Sharp on a sequence of frames from a video."""
    
    def __init__(self, video_path, output_path, params, engine=None):
        super().__init__()
        from app.core.sharp_engine import SharpEngine
        self.engine = engine or SharpEngine(logger_callback=self.log_signal.emit)
        self.video_path = video_path
        self.output_path = output_path
        self.params = params
        
    def stop(self):
        self.engine.stop()
        super().stop()
        
    def run(self):
        try:
            self.status_signal.emit(tr("sharp_msg_extract_frames"))
            self.log_signal.emit(tr("sharp_msg_extract_frames"))
            
            video_path = Path(self.video_path)
            output_dir = Path(self.output_path)
            
            # 1. Create temporary frames directory
            frames_dir = output_dir / "temp_frames"
            frames_dir.mkdir(parents=True, exist_ok=True)
            
            # Clean directory
            for f in frames_dir.glob("*.png"):
                f.unlink()
                
            skip = max(1, int(self.params.get("skip_frames", 1)))

            # 2. Extract frames using ffmpeg
            ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
            cmd = [
                ffmpeg_bin, "-y", "-i", str(video_path),
                "-vf", f"select=not(mod(n\\,{skip}))",
                "-vsync", "vfr", "-q:v", "1",
                str(frames_dir / "frame_%04d.png")
            ]
            self.log_signal.emit(f"Running: {' '.join(cmd)}")
            
            env = os.environ.copy()

            try:
                result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            except FileNotFoundError:
                self.log_signal.emit("Erreur : FFmpeg introuvable. Installez-le via Homebrew : brew install ffmpeg")
                self.finished_signal.emit(False, "FFmpeg non installé.")
                return
            if result.returncode != 0:
                self.log_signal.emit(f"FFmpeg error: {result.stderr}")
                self.finished_signal.emit(False, tr("sharp_err_ffmpeg"))
                return
                
            # Count extracted frames
            frames = sorted(list(frames_dir.glob("*.png")))
            total_frames = len(frames)
            
            if total_frames == 0:
                self.finished_signal.emit(False, "Aucune frame extraite. Vérifiez la vidéo ou le frame skip.")
                return
                
            self.log_signal.emit(f"Total frames extraites: {total_frames}")
            
            # 3. Process each frame with SHARP
            success_count = 0
            for current_idx, frame_path in enumerate(frames):
                if self.isInterruptionRequested():
                    self.log_signal.emit("--- Arrêté par l'utilisateur ---")
                    break
                    
                display_idx = current_idx + 1
                self.status_signal.emit(tr("sharp_msg_process_frame", display_idx, total_frames))
                self.log_signal.emit(f"Processing frame {display_idx}/{total_frames}: {frame_path.name}")
                
                # Output dir for this frame
                frame_out_dir = output_dir / frame_path.stem
                
                # Predict
                returncode = self.engine.predict(str(frame_path), str(frame_out_dir), self.params)
                
                if returncode == 0:
                    # 4. Copy the resulting PLY to the main dir
                    ply_files = list(frame_out_dir.rglob("*.ply"))
                    if ply_files:
                        first_ply = ply_files[0]
                        dest_ply = output_dir / f"{frame_path.stem}.ply"
                        shutil.copy2(first_ply, dest_ply)
                        self.log_signal.emit(f"Saved: {dest_ply.name}")
                        success_count += 1
                        
                # Progress update
                progress = int((display_idx / total_frames) * 100)
                self.progress_signal.emit(progress)
                
                # Cleanup temp dir for frame
                if frame_out_dir.exists():
                    shutil.rmtree(frame_out_dir)
                    
            if success_count > 0:
                self.finished_signal.emit(True, f"Conversion Video -> PLY terminée. {success_count}/{total_frames} frames traitées avec succès.")
            else:
                self.finished_signal.emit(False, "Aucune frame n'a pu être traitée par SHARP.")

        except Exception as e:
            self.log_signal.emit(f"EXCEPTION: {e}\n{traceback.format_exc()}")
            self.finished_signal.emit(False, str(e))
        finally:
            # 5. Cleanup temp frames
            if 'frames_dir' in locals() and frames_dir.exists():
                shutil.rmtree(frames_dir)


# ---------------------------------------------------------------------
# 4DGS WORKER
# ---------------------------------------------------------------------
from app.core.four_dgs_engine import FourDGSEngine

class FourDGSWorker(BaseWorker):
    def __init__(self, videos_dir, output_dir, fps=5, engine=None):
        super().__init__()
        self.videos_dir = videos_dir
        self.output_dir = output_dir
        self.fps = fps
        # DIP : Injection
        self.engine = engine or FourDGSEngine(
            logger_callback=self.log_signal.emit,
            status_callback=self.status_signal.emit
        )

    def run(self):
        self.log_signal.emit("--- Démarrage 4DGS ---")

        
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
        if self.engine:
            self.engine.stop()
        super().stop()
