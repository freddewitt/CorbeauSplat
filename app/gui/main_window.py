import os
import sys
import json
import shutil
import send2trash
from pathlib import Path
from app.core.system import resolve_project_root, resolve_binary
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget, QMessageBox, QFileDialog, QApplication, QLabel, QProgressDialog
)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import QTimer, Qt
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
        self.config_tab.saveConfigRequested.connect(self.save_config)
        self.config_tab.loadConfigRequested.connect(self.load_config)
        self.config_tab.openBrushRequested.connect(self.open_in_brush)
        self.config_tab.deleteDatasetRequested.connect(self.delete_dataset)
        self.config_tab.quitRequested.connect(self.close)
        self.config_tab.relaunchRequested.connect(self.restart_application)
        self.config_tab.resetRequested.connect(self.reset_factory)
        
        self.brush_tab.trainRequested.connect(self.train_brush)
        self.brush_tab.stopRequested.connect(self.stop_brush)
        

        
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
        # Mettre à jour avec les params de l'onglet config si nécessaire
        # Pour l'instant undistort_images est le seul qui pourrait être cross-tab, 
        # mais il est géré dans ConfigTab pour l'action. 
        # ColmapParams l'attend, donc on le set.
        params.undistort_images = self.config_tab.get_undistort()
        return params

    def get_extractor_360_config(self):
        """Combines params from Extractor Tab with Enabled state from Config Tab"""
        params = self.extractor_360_tab.get_params()
        # Override enabled state by the checkbox in Config Tab
        params["enabled"] = self.config_tab.check_source_360.isChecked()
        return params
        
    def process(self):
        """Lance le traitement"""
        input_path = self.config_tab.get_input_path()
        output_path = self.config_tab.get_output_path()
        
        if not input_path or not output_path:
            QMessageBox.critical(self, tr("msg_error"), 
                               tr("err_no_paths"))
            return
            
        self.config_tab.set_processing_state(True)
        self.logs_tab.clear_log()
        self.logs_tab.append_log(tr("msg_processing"))
        
        input_type = self.config_tab.get_input_type()
        project_name = self.config_tab.get_project_name()
        
        self.worker = ColmapWorker(
            self.get_current_params(),
            input_path,
            output_path,
            input_type,
            self.config_tab.get_fps(),
            project_name,
            upscale_params=self.config_tab.get_upscale_config(
                self.upscale_tab.get_params()
            ),
            extractor_360_params=self.get_extractor_360_config()
        )
        
        self.worker.log_signal.connect(self.logs_tab.append_log)
        # Pour simplifier, on n'a pas de progress bar globale ici car elle était dans le layout principal avant.
        # On pourrait l'ajouter dans ConfigTab ou en bas de MainWindow. 
        # Pour l'instant, on laisse le log parler.
        self.worker.finished_signal.connect(self.on_finished)
        
        self.worker.start()
        
    def stop_process(self):
        """Arrête le processus en cours"""
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, tr("msg_warning"),
                tr("confirm_stop"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.logs_tab.append_log(tr("msg_stopping"))
                self.worker.stop()
        
    def on_finished(self, success, message):
        """Fin du traitement"""
        self.config_tab.set_processing_state(False)
        
        if success:
            self.logs_tab.append_log("COLMAP termine avec succes.")
            
            # Auto-launch Brush?
            if self.config_tab.get_auto_brush():
                self.logs_tab.append_log("Lancement automatique de Brush...")
                self.train_brush()
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
                
    def save_config(self):
        """Sauvegarde la configuration"""
        filename, _ = QFileDialog.getSaveFileName(
            self, tr("btn_save_cfg"),
            "", "JSON (*.json)"
        )
        
        if filename:
            params = self.get_current_params()
            config = params.to_dict()
            config['fps'] = self.config_tab.get_fps()
            config['input_path'] = self.config_tab.get_input_path()
            config['output_path'] = self.config_tab.get_output_path()
            config['input_type'] = self.config_tab.get_input_type()
            
            with open(filename, 'w') as f:
                json.dump(config, f, indent=2)
                
            QMessageBox.information(self, tr("msg_success"), "Configuration sauvegardee!")
            
    def load_config(self):
        """Charge une configuration"""
        filename, _ = QFileDialog.getOpenFileName(
            self, tr("btn_load_cfg"),
            "", "JSON (*.json)"
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    config = json.load(f)
                    
                # Load params
                params = ColmapParams.from_dict(config)
                self.params_tab.set_params(params)
                
                # Load config tab specific
                if 'input_path' in config: self.config_tab.set_input_path(config['input_path'])
                if 'output_path' in config: self.config_tab.set_output_path(config['output_path'])
                if 'fps' in config: self.config_tab.set_fps(config['fps'])
                if 'input_type' in config: self.config_tab.set_input_type(config['input_type'])
                if 'undistort_images' in config: self.config_tab.set_undistort(config['undistort_images'])
                
                QMessageBox.information(self, tr("msg_success"), "Configuration chargee!")
                
            except Exception as e:
                QMessageBox.critical(self, tr("msg_error"), f"Erreur de chargement:\n{str(e)}")
                
    def open_in_brush(self):
        """Ouvre le dataset dans Brush"""
        output_dir_str = self.config_tab.get_output_path()
        if not output_dir_str:
            QMessageBox.warning(self, tr("msg_warning"), "Aucun dossier de sortie selectionne")
            return
        
        output_dir = Path(output_dir_str)
        if not output_dir.exists():
            QMessageBox.warning(self, tr("msg_warning"), tr("err_path_not_exists"))
            return
            
        sparse_path = output_dir / "sparse" / "0"
        
        if sparse_path.exists():
            msg = f"{tr('success_created', '')}\n\nOuvrez Brush et chargez:\n{output_dir}\n\n"
            msg += "Structure:\n"
            msg += f"- sparse/0/ (reconstruction COLMAP)\n"
            if (output_dir / "images").exists():
                msg += f"- images/ (images sources)\n"
            msg += f"- brush_config.json (configuration)"
        else:
            msg = f"Dataset incomplet\n\nDossier: {output_dir}\n\nLa reconstruction n'est peut-etre pas terminee."
            
        QMessageBox.information(self, tr("btn_open_brush"), msg)

    def train_brush(self):
        """Lance l'entrainement Brush"""
        brush_params = self.brush_tab.get_params()
        
        if brush_params.get("independent"):
            # Mode Indépendant
            input_path_str = brush_params.get("input_path")
            
            if not input_path_str:
                 QMessageBox.critical(self, tr("msg_error"), "Veuillez selectionner un dossier Dataset valide.")
                 return
                 
            input_path = Path(input_path_str)
            if not input_path.exists():
                 QMessageBox.critical(self, tr("msg_error"), "Veuillez selectionner un dossier Dataset valide.")
                 return
                 
            # Brush output logic in manual mode:
            # Force output to input/checkpoints
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
            
        # Determine root dir
        root_dir = resolve_project_root()
        
        # Prepare command
        python = sys.executable
        main_py = root_dir / "main.py"
        
        args = [python, str(main_py)] + sys.argv[1:]
        
        print(f"Relaunching via execv: {args}")
        
        # Sur Unix (macOS/Linux), execv remplace le processus actuel.
        # C'est beaucoup plus propre pour des relaunchs successifs.
        if sys.platform != "win32":
            try:
                os.execv(python, args)
            except Exception as e:
                print(f"execv failed: {e}. Falling back to Popen.")
                
        # Fallback pour Windows ou si execv échoue
        import subprocess
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

