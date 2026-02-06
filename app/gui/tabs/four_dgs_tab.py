
import os
import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGroupBox,
    QFormLayout, QCheckBox, QSpinBox, QMessageBox, QFileDialog, QTextEdit, QProgressBar, QApplication, QProgressDialog
)
from PyQt6.QtCore import pyqtSignal, Qt, QThread
from app.core.i18n import tr
from app.gui.widgets.drop_line_edit import DropLineEdit
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

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Header
        info = QLabel(tr("four_dgs_header"))
        info.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 5px;")
        layout.addWidget(info)
        
        desc = QLabel(tr("four_dgs_desc"))
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #aaa; margin-bottom: 10px;")
        layout.addWidget(desc)

        # Activation Group
        self.chk_activate = QCheckBox(tr("four_dgs_activate"))
        self.chk_activate.setStyleSheet("font-weight: bold; padding: 5px;")
        self.chk_activate.clicked.connect(self.on_toggle_activation)
        layout.addWidget(self.chk_activate)

        # Main Controls Group (Disabled by default)
        self.controls_group = QGroupBox("Configuration")
        form_layout = QFormLayout()

        # Source
        self.input_edit = DropLineEdit()
        self.input_edit.setPlaceholderText(tr("four_dgs_files_ph"))
        input_layout = QHBoxLayout()
        input_layout.addWidget(self.input_edit)
        btn_browse_in = QPushButton(tr("btn_browse"))
        btn_browse_in.clicked.connect(self.browse_input)
        input_layout.addWidget(btn_browse_in)
        form_layout.addRow(tr("four_dgs_group_src"), input_layout)

        # Destination
        self.output_edit = DropLineEdit()
        self.output_edit.setPlaceholderText("~/CORBEAU_OUTPUT/4dgs_project")
        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_edit)
        btn_browse_out = QPushButton(tr("btn_browse"))
        btn_browse_out.clicked.connect(self.browse_output)
        output_layout.addWidget(btn_browse_out)
        form_layout.addRow(tr("four_dgs_group_dst"), output_layout)

        # FPS
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(5)
        form_layout.addRow(tr("four_dgs_lbl_fps"), self.fps_spin)

        self.controls_group.setLayout(form_layout)
        layout.addWidget(self.controls_group)

        # Actions
        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton("Lancer Préparation 4DGS") # TODO: i18n key logic
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
        d = QFileDialog.getExistingDirectory(self, "Choisir dossier Vidéos")
        if d: self.input_edit.setText(d)

    def browse_output(self):
        d = QFileDialog.getExistingDirectory(self, "Choisir destination")
        if d: self.output_edit.setText(d)

    def run_process(self):
        src = self.input_edit.text().strip()
        dst = self.output_edit.text().strip()
        
        if not src or not dst:
            QMessageBox.warning(self, tr("msg_warning"), "Veuillez sélectionner les dossiers source et destination.")
            return

        if not os.path.exists(src):
             QMessageBox.warning(self, tr("msg_warning"), "Le dossier source n'existe pas.")
             return
             
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.log_view.clear()
        
        self.worker = FourDGSWorker(src, dst, self.fps_spin.value())
        self.worker.log_message.connect(self.append_log)
        self.worker.finished_signal.connect(self.on_process_finished)
        self.worker.start()

    def stop_process(self):
        if self.worker:
            self.worker.stop()
            self.btn_stop.setEnabled(False)
            self.append_log(">>> Arrêt demandé...")

    def on_process_finished(self, success, message):
        self.btn_run.setEnabled(True)
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
