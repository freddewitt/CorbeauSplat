
from pathlib import Path
import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGroupBox,
    QFormLayout, QCheckBox, QSpinBox, QMessageBox, QFileDialog, QTextEdit, QProgressBar, QApplication, QProgressDialog
)
from PyQt6.QtCore import pyqtSignal, Qt, QThread
from app.core.i18n import tr, add_language_observer
from app.gui.widgets.drop_line_edit import DropLineEdit
from app.gui.widgets.dialog_utils import get_existing_directory
from app.gui.workers import FourDGSWorker
from app.core.system import resolve_binary

class FourDGSTab(QWidget):
    """
    Tab for 4DGS Dataset Preparation.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.init_ui()
        add_language_observer(self.retranslate_ui)

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Header
        self.lbl_header = QLabel(tr("four_dgs_header"))
        self.lbl_header.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 5px;")
        layout.addWidget(self.lbl_header)
        
        self.lbl_desc = QLabel(tr("four_dgs_desc"))
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setStyleSheet("color: #aaa; margin-bottom: 10px;")
        layout.addWidget(self.lbl_desc)

        # Activation Group
        self.chk_activate = QCheckBox(tr("four_dgs_activate"))
        self.chk_activate.setStyleSheet("font-weight: bold; padding: 5px;")
        self.chk_activate.clicked.connect(self.on_toggle_activation)
        layout.addWidget(self.chk_activate)

        # Main Controls Group (Disabled by default)
        self.controls_group = QGroupBox(tr("four_dgs_group_cfg", "Configuration"))
        form_layout = QFormLayout()

        # Source
        self.input_edit = DropLineEdit()
        self.input_edit.setPlaceholderText(tr("four_dgs_files_ph"))
        input_layout = QHBoxLayout()
        input_layout.addWidget(self.input_edit)
        self.btn_browse_in = QPushButton(tr("btn_browse"))
        self.btn_browse_in.clicked.connect(self.browse_input)
        input_layout.addWidget(self.btn_browse_in)
        self.lbl_src = QLabel(tr("four_dgs_group_src"))
        form_layout.addRow(self.lbl_src, input_layout)

        # Destination
        self.output_edit = DropLineEdit()
        self.output_edit.setPlaceholderText("~/CORBEAU_OUTPUT/4dgs_project")
        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_edit)
        self.btn_browse_out = QPushButton(tr("btn_browse"))
        self.btn_browse_out.clicked.connect(self.browse_output)
        output_layout.addWidget(self.btn_browse_out)
        self.lbl_dst = QLabel(tr("four_dgs_group_dst"))
        form_layout.addRow(self.lbl_dst, output_layout)

        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(5)
        self.lbl_fps = QLabel(tr("four_dgs_lbl_fps"))
        form_layout.addRow(self.lbl_fps, self.fps_spin)

        self.controls_group.setLayout(form_layout)
        layout.addWidget(self.controls_group)

        # Actions
        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton(tr("four_dgs_btn_run", "Lancer Préparation 4DGS"))
        self.btn_run.setFixedHeight(40)
        self.btn_run.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold;")
        self.btn_run.clicked.connect(self.run_process)
        btn_layout.addWidget(self.btn_run)
        
        self.btn_stop = QPushButton(tr("four_dgs_btn_stop"))
        self.btn_stop.setFixedHeight(40)
        self.btn_stop.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold;")
        self.btn_stop.clicked.connect(self.stop_process)
        self.btn_stop.setEnabled(False)
        btn_layout.addWidget(self.btn_stop)
        
        self.btn_colmap = QPushButton(tr("four_dgs_btn_colmap"))
        self.btn_colmap.setFixedHeight(40)
        self.btn_colmap.setStyleSheet("background-color: #3498db; color: white; font-weight: bold;")
        self.btn_colmap.clicked.connect(self.run_colmap_only)
        btn_layout.addWidget(self.btn_colmap)
        
        layout.addLayout(btn_layout)

        # Logs
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("background-color: #222; color: #eee; font-family: monospace; font-size: 11px;")
        layout.addWidget(self.log_view)

        # Initial State
        self.controls_group.setEnabled(False)
        self.btn_run.setEnabled(False)
        
        # Check if already active/installed (Check persistence or file existence)
        # We check simply if 'ns-process-data' is in path, implying activation
        import shutil
        if shutil.which("ns-process-data"):
            self.chk_activate.setChecked(True)
            self.controls_group.setEnabled(True)
            self.btn_run.setEnabled(True)

    def on_toggle_activation(self):
        if self.chk_activate.isChecked():
            # Check dependency
            import shutil
            if not shutil.which("ns-process-data"):
                reply = QMessageBox.question(
                    self, 
                    "Installation Requise", 
                    tr("msg_install_nerf"),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.install_dependencies()
                else:
                    self.chk_activate.setChecked(False)
            else:
                 self.controls_group.setEnabled(True)
                 self.btn_run.setEnabled(True)
        else:
            self.controls_group.setEnabled(False)
            self.btn_run.setEnabled(False)

    def install_dependencies(self):
        # Install nerfstudio pip package
        progress = QProgressDialog("Installation de Nerfstudio...", "Annuler", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        QApplication.processEvents()
        
        try:
            # We use subprocess to call pip
            # Make sure we use the current python executable
            cmd = [sys.executable, "-m", "pip", "install", "nerfstudio"]
            subprocess.check_call(cmd)
            
            QMessageBox.information(self, tr("msg_success"), "Installation terminée. Veuillez redémarrer l'application.")
            self.controls_group.setEnabled(True)
            self.btn_run.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, tr("msg_error"), f"Erreur installation: {e}")
            self.chk_activate.setChecked(False)
        finally:
            progress.close()

    def browse_input(self):
        d = get_existing_directory(self, "Choisir dossier Vidéos")
        if d:
            self.input_edit.setText(d)

    def browse_output(self):
        d = get_existing_directory(self, "Choisir destination")
        if d:
            self.output_edit.setText(d)

    def run_process(self):
        src = self.input_edit.text().strip()
        dst = self.output_edit.text().strip()
        
        if not src or not dst:
            QMessageBox.warning(self, tr("msg_warning"), "Veuillez sélectionner les dossiers source et destination.")
            return

        if not Path(src).exists():
             QMessageBox.warning(self, tr("msg_warning"), "Le dossier source n'existe pas.")
             return
             
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.log_view.clear()
        
        self.worker = FourDGSWorker(src, dst, self.fps_spin.value())
        self.worker.log_signal.connect(self.append_log)
        self.worker.finished_signal.connect(self.on_process_finished)
        self.worker.start()

    def run_colmap_only(self):
        dst = self.output_edit.text().strip()
        if not dst:
            QMessageBox.warning(self, tr("msg_warning"), "Veuillez sélectionner un dossier destination.")
            return
            
        if not Path(dst).exists():
             QMessageBox.warning(self, tr("msg_warning"), "Le dossier destination n'existe pas.")
             return
             
        self.btn_run.setEnabled(False)
        self.btn_colmap.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.log_view.clear()
        
        self.append_log(tr("four_dgs_msg_colmap_start", dst))
        
        # Use existing worker but with a flag? Or just call engine directly if synchronous?
        # Better use worker to avoid blocking.
        self.worker = FourDGSWorker(None, dst, self.fps_spin.value()) # None for videos_dir signals colmap only
        self.worker.log_signal.connect(self.append_log)
        self.worker.finished_signal.connect(self.on_process_finished)
        self.worker.start()

    def stop_process(self):
        if self.worker:
            self.worker.stop()
            self.btn_stop.setEnabled(False)
            self.append_log(">>> Arrêt demandé...")

    def on_process_finished(self, success, message):
        self.btn_run.setEnabled(True)
        self.btn_colmap.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if success:
            QMessageBox.information(self, tr("msg_success"), message)
        else:
             if "Arrêté" not in message:
                QMessageBox.critical(self, tr("msg_error"), message)
        self.worker = None

    def append_log(self, text):
        self.log_view.append(text)
        # Auto scroll
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def get_params(self):
        return {
            "active": self.chk_activate.isChecked(),
            "input_path": self.input_edit.text(),
            "output_path": self.output_edit.text(),
            "fps": self.fps_spin.value()
        }

    def set_params(self, params):
        if not params: return
        if "active" in params:
            self.chk_activate.setChecked(params["active"])
            self.on_toggle_activation()
        if "input_path" in params: self.input_edit.setText(params["input_path"])
        if "output_path" in params: self.output_edit.setText(params["output_path"])
        if "fps" in params: self.fps_spin.setValue(params["fps"])

    def get_state(self):
        return self.get_params()
        
    def set_state(self, state):
        self.set_params(state)

    def retranslate_ui(self):
        """Update texts when language changes"""
        self.lbl_header.setText(tr("four_dgs_header"))
        self.lbl_desc.setText(tr("four_dgs_desc"))
        self.chk_activate.setText(tr("four_dgs_activate"))
        self.controls_group.setTitle(tr("four_dgs_group_cfg", "Configuration"))
        self.lbl_src.setText(tr("four_dgs_group_src"))
        self.input_edit.setPlaceholderText(tr("four_dgs_files_ph"))
        self.lbl_dst.setText(tr("four_dgs_group_dst"))
        self.btn_browse_in.setText(tr("btn_browse"))
        self.btn_browse_out.setText(tr("btn_browse"))
        self.lbl_fps.setText(tr("four_dgs_lbl_fps"))
        self.btn_run.setText(tr("four_dgs_btn_run", "Lancer Préparation 4DGS"))
        self.btn_stop.setText(tr("four_dgs_btn_stop"))
        self.btn_colmap.setText(tr("four_dgs_btn_colmap"))
