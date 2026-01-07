import os
import sys
import json
import shutil
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget, QMessageBox, QFileDialog, QApplication, QLabel
)
from app.core.params import ColmapParams
from app.core.i18n import tr
from app.gui.styles import set_dark_theme
from app.gui.tabs.config_tab import ConfigTab
from app.gui.tabs.params_tab import ParamsTab
from app.gui.tabs.logs_tab import LogsTab
from app.gui.tabs.brush_tab import BrushTab
from app.gui.tabs.sharp_tab import SharpTab
from app.gui.tabs.superplat_tab import SuperSplatTab
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
        
        self.sharp_tab = SharpTab()
        self.tabs.addTab(self.sharp_tab, "Apple Sharp")

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
        
        self.brush_tab.trainRequested.connect(self.train_brush)
        self.brush_tab.stopRequested.connect(self.stop_brush)
        
        self.sharp_tab.predictRequested.connect(self.run_sharp)
        self.sharp_tab.stopRequested.connect(self.stop_sharp)
        
    def get_current_params(self):
        """Récupère les paramètres actuels de l'onglet params et ajoute ceux de config"""
        params = self.params_tab.get_params()
        # Mettre à jour avec les params de l'onglet config si nécessaire
        # Pour l'instant undistort_images est le seul qui pourrait être cross-tab, 
        # mais il est géré dans ConfigTab pour l'action. 
        # ColmapParams l'attend, donc on le set.
        params.undistort_images = self.config_tab.get_undistort()
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
            project_name
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
        """Supprime un dataset existant"""
        output_dir = self.config_tab.get_output_path()
        
        if not output_dir:
            QMessageBox.warning(self, tr("msg_warning"), tr("err_no_paths"))
            return
        
        if not os.path.exists(output_dir):
            QMessageBox.information(self, "Info", tr("err_path_not_exists"))
            return
            
        has_dataset = (
            os.path.exists(os.path.join(output_dir, "database.db")) or
            os.path.exists(os.path.join(output_dir, "sparse")) or
            os.path.exists(os.path.join(output_dir, "images"))
        )
        
        if not has_dataset:
            reply = QMessageBox.question(
                self, tr("msg_warning"),
                tr("confirm_delete_nodata", output_dir),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
        else:
            reply = QMessageBox.question(
                self, tr("msg_warning"),
                tr("confirm_delete", output_dir),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
        if reply == QMessageBox.StandardButton.Yes:
            try:
                shutil.rmtree(output_dir)
                self.logs_tab.append_log(f"Dataset supprime: {output_dir}") # Keep debug log as it is or add key? Let's leave for now
                QMessageBox.information(self, tr("msg_success"), "Dataset supprime avec succes")
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
        output_dir = self.config_tab.get_output_path()
        if not output_dir:
            QMessageBox.warning(self, tr("msg_warning"), "Aucun dossier de sortie selectionne")
            return
        
        if not os.path.exists(output_dir):
            QMessageBox.warning(self, tr("msg_warning"), tr("err_path_not_exists"))
            return
            
        sparse_path = os.path.join(output_dir, "sparse", "0")
        
        if os.path.exists(sparse_path):
            msg = f"{tr('success_created', '')}\n\nOuvrez Brush et chargez:\n{output_dir}\n\n"
            msg += "Structure:\n"
            msg += f"- sparse/0/ (reconstruction COLMAP)\n"
            if os.path.exists(os.path.join(output_dir, "images")):
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
            input_path = brush_params.get("input_path")
            
            if not input_path or not os.path.exists(input_path):
                 QMessageBox.critical(self, tr("msg_error"), "Veuillez selectionner un dossier Dataset valide.")
                 return
                 
            # Brush output logic in manual mode:
            # Force output to input/checkpoints
            output_path = os.path.join(input_path, "checkpoints")
            os.makedirs(output_path, exist_ok=True)
            
        else:
            # Mode Automatique (via Colmap output)
            colmap_out_root = self.config_tab.get_output_path()
            project_name = self.config_tab.get_project_name()
            
            if not colmap_out_root or not os.path.exists(colmap_out_root):
                 QMessageBox.critical(self, tr("msg_error"), "Le dossier de sortie racine n'existe pas.")
                 return
                 
            # Le dataset est dans root/project_name
            dataset_path = os.path.join(colmap_out_root, project_name)
            
            if not os.path.exists(dataset_path):
                QMessageBox.critical(self, tr("msg_error"), f"Le dossier du projet n'existe pas:\n{dataset_path}\nAvez-vous lancé la création du dataset ?")
                return
                
            input_path = dataset_path
            output_path = os.path.join(dataset_path, "checkpoints")
            os.makedirs(output_path, exist_ok=True)
        
        self.brush_tab.set_processing_state(True)
        self.logs_tab.append_log(tr("msg_brush_start", input_path))
        self.logs_tab.append_log(tr("msg_brush_out", output_path))
        
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
            if "Arrete" not in message: # TODO: standardize cancel message
                QMessageBox.warning(self, tr("msg_error"), f"Erreur Brush:\n{message}")

    def run_sharp(self):
        """Lance Sharp"""
        params = self.sharp_tab.get_params()
        input_path = params.get("input_path")
        output_path = params.get("output_path")
        
        if not input_path or not os.path.exists(input_path):
             QMessageBox.critical(self, tr("msg_error"), "Veuillez selectionner un dossier d'images valide.")
             return
        if not output_path:
             QMessageBox.critical(self, tr("msg_error"), "Veuillez selectionner un dossier de sortie.")
             return
             
        self.sharp_tab.set_processing_state(True)
        self.logs_tab.append_log(f"--- Lancement Apple ML Sharp ---")
        self.logs_tab.append_log(f"Input: {input_path}")
        self.logs_tab.append_log(f"Output: {output_path}")
        
        self.sharp_worker = SharpWorker(input_path, output_path, params)
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
        """Redémarre l'application"""
        self.save_session_state()
        QApplication.quit()
        # Redémarrer le processus actuel
        python = sys.executable
        os.execl(python, python, *sys.argv)

    # --- Session Persistence ---

    def get_session_file(self):
        # Utilise config.json à la racine de l'application ou dans le dossier user
        # On va utiliser config.json localement car c'était celui utilisé par l'app.
        # Mais attention .gitignore l'ignore, donc c'est parfait pour du local state.
        return os.path.join(os.getcwd(), "config.json")

    def save_session_state(self):
        """Sauvegarde l'état de l'application"""
        state = {
            "language": self.config_tab.combo_lang.currentData(),
            "config": self.config_tab.get_state(),
            "colmap_params": self.params_tab.get_params().to_dict(),
            "brush_params": self.brush_tab.get_params(),
            "sharp_params": self.sharp_tab.get_params(),
            # "supersplat": ... (si besoin)
        }
        
        try:
            with open(self.get_session_file(), 'w') as f:
                json.dump(state, f, indent=2)
            # print("Session sauvegardée.")
        except Exception as e:
            print(f"Erreur sauvegarde session: {e}")

    def load_session_state(self):
        """Charge l'état précédent"""
        session_file = self.get_session_file()
        if not os.path.exists(session_file):
            return
            
        try:
            with open(session_file, 'r') as f:
                state = json.load(f)
                
            if "config" in state:
                self.config_tab.set_state(state["config"])
                
            if "colmap_params" in state:
                self.params_tab.set_params(ColmapParams.from_dict(state["colmap_params"]))
                
            if "brush_params" in state:
                self.brush_tab.set_params(state["brush_params"])
                
            if "sharp_params" in state:
                self.sharp_tab.set_params(state["sharp_params"])
                
             # print("Session chargée.")
        except Exception as e:
            print(f"Erreur chargement session: {e}")

    def closeEvent(self, event):
        """Appelé à la fermeture de la fenêtre"""
        self.save_session_state()
        event.accept()

