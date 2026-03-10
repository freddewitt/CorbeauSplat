import os
import sys
import json
from pathlib import Path
from app.core.system import resolve_project_root
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget, QMessageBox, QFileDialog, QApplication, QLabel
)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt
from app.core.params import ColmapParams
from app.core.engine import ColmapEngine
from app.core.i18n import tr, add_language_observer

from app.gui.styles import set_dark_theme
from app.gui.tabs.config_tab import ConfigTab
from app.gui.tabs.params_tab import ParamsTab
from app.gui.tabs.logs_tab import LogsTab
from app.gui.tabs.brush_tab import BrushTab
from app.gui.tabs.sharp_tab import SharpTab
from app.gui.tabs.superplat_tab import SuperSplatTab
from app.gui.tabs.upscale_tab import UpscaleTab
from app.gui.tabs.four_dgs_tab import FourDGSTab
from app.gui.tabs.extractor_360_tab import Extractor360Tab
from app.gui.workers import ColmapWorker, BrushWorker, SharpWorker
from app import VERSION

class ColmapGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.brush_worker = None
        self.sharp_worker = None
        self.init_ui()
        set_dark_theme(QApplication.instance())
        add_language_observer(self.retranslate_ui)
        self.load_session_state()
        


    def init_ui(self):
        """Initialise l'interface"""
        self.setWindowTitle(tr("app_title"))
        self.setGeometry(100, 100, 1000, 800)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Init Tabs
        self.config_tab = ConfigTab()
        self.tabs.addTab(self.config_tab, tr("tab_config"))
        
        self.params_tab = ParamsTab()
        self.tabs.addTab(self.params_tab, tr("tab_params"))
        

        
        self.brush_tab = BrushTab()
        self.tabs.addTab(self.brush_tab, tr("tab_brush"))
        
        self.superplat_tab = SuperSplatTab()
        self.tabs.addTab(self.superplat_tab, tr("tab_supersplat"))

        self.upscale_tab = UpscaleTab()
        self.tabs.addTab(self.upscale_tab, tr("tab_upscale"))
        
        self.sharp_tab = SharpTab()
        self.tabs.addTab(self.sharp_tab, tr("tab_sharp"))
        


        self.four_dgs_tab = FourDGSTab()
        self.tabs.addTab(self.four_dgs_tab, tr("tab_four_dgs"))

        self.extractor_360_tab = Extractor360Tab()
        self.tabs.addTab(self.extractor_360_tab, tr("tab_360"))

        self.logs_tab = LogsTab()
        self.tabs.addTab(self.logs_tab, tr("tab_logs"))
        
        # Discreet Version Label (Status Bar)
        version_label = QLabel(f"v{VERSION}")
        version_label.setStyleSheet("color: #666666; font-size: 10px; padding: 2px;")
        self.statusBar().addPermanentWidget(version_label)
        self.statusBar().setStyleSheet("background-color: transparent;")
        
        # Connect signals
        self.config_tab.processRequested.connect(self.process)
        self.config_tab.stopRequested.connect(self.stop_process)
        self.config_tab.deleteDatasetRequested.connect(self.delete_dataset)
        self.config_tab.quitRequested.connect(self.close)
        self.config_tab.relaunchRequested.connect(self.restart_application)
        self.config_tab.resetRequested.connect(self.reset_factory)
        
        self.brush_tab.trainRequested.connect(self.train_brush)
        self.brush_tab.stopRequested.connect(self.stop_brush)
        self.brush_tab.restartRequested.connect(self.restart_application)
        

        
        self.sharp_tab.predictRequested.connect(self.run_sharp)
        self.sharp_tab.stopRequested.connect(self.stop_sharp)
        
        # Apply visual hierarchy to utility tabs
        self.apply_tab_styling()

    def retranslate_ui(self):
        """Update window title and tab names when language changes"""
        self.setWindowTitle(tr("app_title"))
        
        # Tabs are identified by index, but we can match them with our members
        tab_names = {
            self.config_tab: tr("tab_config"),
            self.params_tab: tr("tab_params"),
            self.brush_tab: tr("tab_brush"),
            self.superplat_tab: tr("tab_supersplat"),
            self.upscale_tab: tr("tab_upscale"),
            self.sharp_tab: tr("tab_sharp"),
            self.four_dgs_tab: tr("tab_four_dgs"),
            self.extractor_360_tab: tr("tab_360"),
            self.logs_tab: tr("tab_logs")
        }
        
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if widget in tab_names:
                self.tabs.setTabText(i, tab_names[widget])
        
        # Re-apply styling (colors etc) as setTabText might reset them in some Qt versions
        self.apply_tab_styling()

    def apply_tab_styling(self):
        """Applies a slightly lighter/muted gray color to secondary/utility tabs"""
        secondary_tabs = [
            self.config_tab,
            self.upscale_tab,
            self.sharp_tab,
            self.four_dgs_tab,
            self.extractor_360_tab,
            self.logs_tab
        ]
        
        tab_bar = self.tabs.tabBar()
        # Light gray text for secondary/option tabs
        secondary_color = QColor("#aaaaaa") 
        
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if widget in secondary_tabs:
                tab_bar.setTabTextColor(i, secondary_color)
            else:
                # Keep main tabs (Params, Brush, SuperSplat) in bright white
                tab_bar.setTabTextColor(i, Qt.GlobalColor.white)
        
    def get_current_params(self):
        """Récupère les paramètres actuels de l'onglet params et ajoute ceux de config"""
        params = self.params_tab.get_params()
        params.undistort_images = self.config_tab.get_undistort()
        return params

    def get_upscale_config(self):
        """Combine global upscale settings with the toggle from Config Tab"""
        upscale_params = self.upscale_tab.get_params()
        upscale_params["active"] = self.config_tab.get_upscale()
        # For Sharp worker, it expects 'upscale' key
        upscale_params["upscale"] = upscale_params["active"]
        return upscale_params

    def get_extractor_360_config(self):
        """Combines params from Extractor Tab with current mode"""
        params = self.extractor_360_tab.get_params()
        params["enabled"] = (self.config_tab.get_training_mode() == "360")
        return params
        
    def process(self):
        """Lance le traitement en fonction du mode sélectionné"""
        input_path = self.config_tab.get_input_path()
        output_path = self.config_tab.get_output_path()
        
        if not input_path or not output_path:
            QMessageBox.critical(self, tr("msg_error"), tr("err_no_paths"))
            return
            
        mode = self.config_tab.get_training_mode()
        self.config_tab.set_processing_state(True)
        self.logs_tab.clear_log()
        
        if mode == "gsplat":
            self.logs_tab.append_log(tr("msg_processing") + " (Gsplat)")
            self.worker = ColmapWorker(
                self.get_current_params(),
                input_path, output_path, self.config_tab.get_input_type(),
                self.config_tab.get_fps(),
                self.config_tab.get_project_name(),
                upscale_params=self.get_upscale_config(),
                extractor_360_params=None # Disabled
            )
            self.worker.log_signal.connect(self.logs_tab.append_log)
            self.worker.progress_signal.connect(self.config_tab.progress_bar.setValue)
            self.worker.status_signal.connect(self.config_tab.lbl_status.setText)
            self.worker.finished_signal.connect(self.on_finished)
            self.worker.start()
            
        elif mode == "sharp":
            self.logs_tab.append_log(tr("msg_processing") + " (ML Sharp)")
            sharp_params = self.sharp_tab.get_params()
            sharp_params.update(self.get_upscale_config())
            
            self.sharp_worker = SharpWorker(input_path, output_path, sharp_params)
            self.sharp_worker.log_signal.connect(self.logs_tab.append_log)
            self.sharp_worker.progress_signal.connect(self.config_tab.progress_bar.setValue)
            self.sharp_worker.status_signal.connect(self.config_tab.lbl_status.setText)
            self.sharp_worker.finished_signal.connect(self.on_sharp_finished)
            self.sharp_worker.start()
            
        elif mode == "360":
            self.logs_tab.append_log(tr("msg_processing") + " (360 Extractor)")
            ext_params = self.extractor_360_tab.get_params()
            ext_params["enabled"] = True
            
            self.worker = ColmapWorker(
                self.get_current_params(),
                input_path, output_path, "video",
                self.config_tab.get_fps(),
                self.config_tab.get_project_name(),
                upscale_params=self.get_upscale_config(),
                extractor_360_params=ext_params
            )
            self.worker.log_signal.connect(self.logs_tab.append_log)
            self.worker.progress_signal.connect(self.config_tab.progress_bar.setValue)
            self.worker.status_signal.connect(self.config_tab.lbl_status.setText)
            self.worker.finished_signal.connect(self.on_finished)
            self.worker.start()
            
        elif mode == "4dgs":
            self.logs_tab.append_log(tr("msg_processing") + " (4DGS)")
            
            # Need to import FourDGSWorker if not already done. It is imported at line 27.
            from app.gui.workers import FourDGSWorker
            self.fourdgs_worker = FourDGSWorker(input_path, output_path, self.config_tab.get_fps())
            self.fourdgs_worker.log_signal.connect(self.logs_tab.append_log)
            self.fourdgs_worker.progress_signal.connect(self.config_tab.progress_bar.setValue)
            self.fourdgs_worker.status_signal.connect(self.config_tab.lbl_status.setText)
            self.fourdgs_worker.finished_signal.connect(self.on_finished)
            self.fourdgs_worker.start()
            
        # self.tabs.setCurrentWidget(self.logs_tab)
        
    def stop_process(self):
        """Arrête le processus en cours"""
        if (self.worker and self.worker.isRunning()) or \
           (self.sharp_worker and self.sharp_worker.isRunning()) or \
           (hasattr(self, 'fourdgs_worker') and self.fourdgs_worker and self.fourdgs_worker.isRunning()):
            
            reply = QMessageBox.question(
                self, tr("msg_warning"), tr("confirm_stop"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.logs_tab.append_log(tr("msg_stopping"))
                if self.worker and self.worker.isRunning(): self.worker.stop()
                if self.sharp_worker and self.sharp_worker.isRunning(): self.sharp_worker.stop()
                if hasattr(self, 'fourdgs_worker') and self.fourdgs_worker and self.fourdgs_worker.isRunning(): self.fourdgs_worker.stop()
        
    def on_finished(self, success, message):
        """Fin du traitement"""
        self.config_tab.set_processing_state(False)
        
        if success:
            self.logs_tab.append_log(tr("msg_success"))

            # Auto-launch Brush?
            if self.config_tab.get_auto_brush():
                self.logs_tab.append_log(tr("msg_brush_start", ""))
                self.train_brush(force_auto=True)
            else:
                QMessageBox.information(self, tr("msg_success"), 
                                      f"{message}\n\n{tr('success_open_brush')}")
        else:
            if "Arrete" not in message:
                QMessageBox.warning(self, tr("msg_error"), f"{tr('msg_error')}:\n{message}")
            
    def delete_dataset(self):
        """Supprime le contenu d'un dataset existant"""
        output_dir_str = self.config_tab.get_output_path()
        project_name = self.config_tab.get_project_name()
        
        if not output_dir_str:
            QMessageBox.warning(self, tr("msg_warning"), tr("err_no_paths"))
            return
        
        output_dir = Path(output_dir_str)
        # 1. Target: output_dir/project_name
        target_path = output_dir / project_name
        
        # 2. Fallback: output_dir (if user pointed directly to it)
        # We check if it looks like a dataset
        if not target_path.exists():
            if (output_dir / "database.db").exists() or (output_dir / "sparse").exists():
                target_path = output_dir
        
        if not target_path.exists():
            QMessageBox.information(self, "Info", tr("err_path_not_exists"))
            return

        # Double check safety: ensure we are deleting a dataset
        has_dataset = (
            (target_path / "database.db").exists() or
            (target_path / "sparse").exists() or
            (target_path / "images").exists()
        )
        
        if not has_dataset:
            reply = QMessageBox.question(
                self, tr("msg_warning"),
                tr("confirm_delete_nodata", str(target_path)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
        else:
            reply = QMessageBox.question(
                self, tr("msg_warning"),
                f"Voulez-vous mettre a la corbeille le contenu du dossier :\n\n{target_path}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
        if reply == QMessageBox.StandardButton.Yes:
            try:
                success, msg = ColmapEngine.delete_project_content(target_path)
                if success:
                    self.logs_tab.append_log(f"Dataset deleted: {target_path}")
                    QMessageBox.information(self, tr("msg_success"), msg)
                else:
                    QMessageBox.critical(self, tr("msg_error"), f"Erreur: {msg}")
            except Exception as e:
                QMessageBox.critical(self, tr("msg_error"), f"Impossible de supprimer le dataset:\n{str(e)}")
                
    def train_brush(self, force_auto=False):
        """Lance l'entrainement Brush"""
        brush_params = self.brush_tab.get_params()
        
        if not force_auto and brush_params.get("independent"):
            # Mode Indépendant
            input_path_str = brush_params.get("input_path")
            
            if not input_path_str:
                 QMessageBox.critical(self, tr("msg_error"), "Veuillez selectionner un dossier Dataset valide.")
                 return
                 
            input_path = Path(input_path_str)
            if not input_path.exists():
                 QMessageBox.critical(self, tr("msg_error"), "Veuillez selectionner un dossier Dataset valide.")
                 return

            # Use custom output path if provided, otherwise default to input/checkpoints
            output_path_str = brush_params.get("output_path", "").strip()
            if output_path_str:
                output_path = Path(output_path_str)
            else:
                output_path = input_path / "checkpoints"
            output_path.mkdir(parents=True, exist_ok=True)
            
        else:
            # Mode Automatique (via Colmap output)
            colmap_out_root_str = self.config_tab.get_output_path()
            project_name = self.config_tab.get_project_name()
            
            if not colmap_out_root_str:
                 QMessageBox.critical(self, tr("msg_error"), "Le dossier de sortie racine n'existe pas.")
                 return
            
            colmap_out_root = Path(colmap_out_root_str)
            if not colmap_out_root.exists():
                 QMessageBox.critical(self, tr("msg_error"), "Le dossier de sortie racine n'existe pas.")
                 return
                 
            # Le dataset est dans root/project_name
            dataset_path = colmap_out_root / project_name
            
            if not dataset_path.exists():
                QMessageBox.critical(self, tr("msg_error"), f"Le dossier du projet n'existe pas:\n{dataset_path}\nAvez-vous lancé la création du dataset ?")
                return
                
            input_path = dataset_path
            output_path = dataset_path / "checkpoints"
            output_path.mkdir(parents=True, exist_ok=True)
        
        self.brush_tab.set_processing_state(True)
        self.logs_tab.append_log(tr("msg_brush_start", str(input_path)))
        self.logs_tab.append_log(tr("msg_brush_out", str(output_path)))
        
        self.brush_worker = BrushWorker(
            input_path,
            output_path,
            brush_params
        )
        
        self.brush_worker.log_signal.connect(self.logs_tab.append_log)
        self.brush_worker.finished_signal.connect(self.on_brush_finished)
        
        self.brush_worker.start()
        
        # Focus logs tab
        self.tabs.setCurrentWidget(self.logs_tab)
        
    def stop_brush(self):
        """Arrête Brush"""
        if hasattr(self, 'brush_worker') and self.brush_worker and self.brush_worker.isRunning():
            self.brush_worker.stop()
            self.logs_tab.append_log("Arrêt de Brush demandé...")

    def on_brush_finished(self, success, message):
        """Fin entrainement Brush"""
        self.brush_tab.set_processing_state(False)
        self.logs_tab.append_log(f"Fin Brush: {message}")
        
        if success:
            QMessageBox.information(self, tr("msg_success"), f"Brush terminé!\n{message}")
        else:
            if "Arrete" not in message:
                QMessageBox.warning(self, tr("msg_error"), f"Erreur Brush:\n{message}")



    def run_sharp(self):
        """Lance Sharp"""
        params = self.sharp_tab.get_params()
        input_path_str = params.get("input_path")
        output_path_str = params.get("output_path")
        
        if not input_path_str:
             QMessageBox.critical(self, tr("msg_error"), "Veuillez selectionner un dossier d'images valide.")
             return
             
        input_path = Path(input_path_str)
        if not input_path.exists():
             QMessageBox.critical(self, tr("msg_error"), "Veuillez selectionner un dossier d'images valide.")
             return
             
        if not output_path_str:
             QMessageBox.critical(self, tr("msg_error"), "Veuillez selectionner un dossier de sortie.")
             return
        
        output_path = Path(output_path_str)
        
        self.sharp_tab.set_processing_state(True)
        self.logs_tab.append_log(f"--- Lancement Apple ML Sharp ---")
        self.logs_tab.append_log(f"Input: {input_path}")
        self.logs_tab.append_log(f"Output: {output_path}")
        
        self.sharp_worker = SharpWorker(str(input_path), str(output_path), params)
        self.sharp_worker.log_signal.connect(self.logs_tab.append_log)
        self.sharp_worker.finished_signal.connect(self.on_sharp_finished)
        self.sharp_worker.start()
        
        self.tabs.setCurrentWidget(self.logs_tab)
        
    def stop_sharp(self):
        """Arrête Sharp"""
        if self.sharp_worker and self.sharp_worker.isRunning():
            self.sharp_worker.stop()
            self.logs_tab.append_log("Arrêt de Sharp demandé...")
            
    def on_sharp_finished(self, success, message):
        """Fin Sharp"""
        self.sharp_tab.set_processing_state(False)
        self.config_tab.set_processing_state(False)
        self.logs_tab.append_log(f"Fin Sharp: {message}")
        
        if success:
            QMessageBox.information(self, tr("msg_success"), f"Sharp terminé!\n{message}")
        else:
            QMessageBox.warning(self, tr("msg_error"), f"Erreur Sharp:\n{message}")

    def restart_application(self):
        """Redémarre l'application de manière plus robuste via execv"""
        try:
            self.save_session_state()
        except Exception as e:
            print(f"Error saving session before restart: {e}")

        import subprocess
        root_dir = resolve_project_root()
        python = sys.executable
        main_py = root_dir / "main.py"

        # Si un binaire engine est manquant (ex: après réinstall Brush),
        # on réinjecte l'étape setup_dependencies --startup avant de relancer.
        engines_dir = root_dir / "engines"
        needs_setup = any([
            not (engines_dir / "brush").exists() and (engines_dir / "brush.version").exists() is False,
            not (engines_dir / "brush").exists(),
        ])

        if needs_setup and sys.platform != "win32":
            print("Reinstall detected: running setup before relaunch...")
            extra_argv = [a for a in sys.argv[1:] if a not in ("--gui",)]
            main_args = " ".join(f'"{a}"' for a in extra_argv)
            cmd = (
                f'sleep 1 && '
                f'"{python}" -m app.scripts.setup_dependencies --startup && '
                f'"{python}" "{main_py}" {main_args}'
            )
            subprocess.Popen(cmd, shell=True, cwd=str(root_dir), start_new_session=True)
            QApplication.quit()
            sys.exit(0)

        # Relance normale
        args = [python, str(main_py)] + sys.argv[1:]
        print(f"Relaunching via execv: {args}")

        if sys.platform != "win32":
            try:
                os.execv(python, args)
            except Exception as e:
                print(f"execv failed: {e}. Falling back to Popen.")

        kwargs = {}
        if sys.platform != "win32":
            kwargs["start_new_session"] = True

        subprocess.Popen(args, cwd=str(root_dir), **kwargs)
        QApplication.quit()
        sys.exit(0)
        
    def reset_factory(self):
        """Supprime les venvs et relance l'installation/application"""
        import subprocess
        
        QApplication.quit()
        
        # Obtenir le chemin de run.command (supposé à la racine)
        root_dir = resolve_project_root()
            
        run_cmd = root_dir / "run.command"
        venv_path = root_dir / ".venv"
        venv_sharp_path = root_dir / ".venv_sharp"
        
        print(f"Reset Factory initie sur: {root_dir}")
        print(f"Commande relance: {run_cmd}")
        
        # On lance une commande shell détachée qui va:
        # 1. Attendre que nous quittions (sleep 2)
        # 2. Supprimer les dossiers venv
        # 3. Relancer run.command
        
        cmd = f"sleep 2 && rm -rf \"{venv_path}\" \"{venv_sharp_path}\" && \"{run_cmd}\" &"
        
        subprocess.Popen(cmd, shell=True, cwd=str(root_dir))
        sys.exit(0)

    # --- Session Persistence ---

    def get_session_file(self) -> Path:
        """Retourne le chemin vers le fichier de session (config.json)"""
        return resolve_project_root() / "config.json"

    def save_session_state(self):
        """Sauvegarde l'état de l'application de manière dynamique"""
        state = {
            "language": self.config_tab.combo_lang.currentData(),
        }
        
        # Collecter l'état de chaque onglet capable de le fournir
        tab_mapping = {
            "config": self.config_tab,
            "colmap_params": self.params_tab,
            "brush_params": self.brush_tab,
            "sharp_params": self.sharp_tab,
            "upscale_params": self.upscale_tab,
            "extractor_360_params": self.extractor_360_tab,
            "four_dgs_params": self.four_dgs_tab,
        }
        
        for key, tab in tab_mapping.items():
            try:
                if hasattr(tab, 'get_state'):
                    state[key] = tab.get_state()
                elif hasattr(tab, 'get_params'):
                    state[key] = tab.get_params()
                    # Si c'est un objet ColmapParams, on le convertit
                    if hasattr(state[key], 'to_dict'):
                        state[key] = state[key].to_dict()
            except Exception as e:
                print(f"Erreur lors de la collecte de l'état pour '{key}': {e}")

        try:
            with open(self.get_session_file(), 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"Erreur sauvegarde session: {e}")

    def load_session_state(self):
        """Charge l'état précédent de manière dynamique"""
        session_file = self.get_session_file()
        if not session_file.exists():
            return
            
        try:
            with open(session_file, 'r') as f:
                state = json.load(f)
                
            tab_mapping = {
                "config": self.config_tab,
                "colmap_params": self.params_tab,
                "brush_params": self.brush_tab,
                "sharp_params": self.sharp_tab,
                "upscale_params": self.upscale_tab,
                "extractor_360_params": self.extractor_360_tab,
                "four_dgs_params": self.four_dgs_tab,
            }
            
            for key, tab in tab_mapping.items():
                if key in state:
                    try:
                        if hasattr(tab, 'set_state'):
                            tab.set_state(state[key])
                        elif hasattr(tab, 'set_params'):
                            # Cas spécial ColmapParams
                            if key == "colmap_params":
                                tab.set_params(ColmapParams.from_dict(state[key]))
                            else:
                                tab.set_params(state[key])
                    except Exception as e:
                        print(f"Erreur lors du chargement de l'état pour '{key}': {e}")

        except Exception as e:
            print(f"Erreur chargement session: {e}")

    def closeEvent(self, event):
        """Appelé à la fermeture de la fenêtre"""
        self.save_session_state()
        event.accept()

