import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QGroupBox, QFileDialog, QSpinBox, QMessageBox, QFormLayout, QCheckBox,
    QProgressDialog, QApplication
)
from PyQt6.QtCore import pyqtSignal, Qt
from app.core.i18n import tr
from app.core.system import is_nerfstudio_installed, install_nerfstudio
from app.core.i18n import tr

class FourDGSTab(QWidget):
    """
    Tab for 4DGS Dataset Preparation.
    Allows selecting a folder of videos (cameras) and processing them into a 4DGS dataset.
    """
    
    processRequested = pyqtSignal()
    stopRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.processing = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        info = QLabel(tr("four_dgs_header"))
        info.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 10px;")
        layout.addWidget(info)
        
        desc = QLabel(tr("four_dgs_desc"))
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #aaa; margin-bottom: 5px;")
        layout.addWidget(desc)

        warning_cuda = QLabel(tr("four_dgs_warning_cuda"))
        warning_cuda.setStyleSheet("color: #e67e22; font-style: italic; margin-bottom: 20px;")
        layout.addWidget(warning_cuda)

        # Activation Checkbox
        self.chk_activate = QCheckBox(tr("four_dgs_activate"))
        self.chk_activate.setStyleSheet("font-weight: bold; padding: 5px;")
        self.chk_activate.clicked.connect(self.on_toggle_activation)
        layout.addWidget(self.chk_activate)

        # Main Content Widget (to disable/enable en masse)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. Source
        src_group = QGroupBox(tr("four_dgs_group_src"))
        src_layout = QHBoxLayout()
        
        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText(tr("four_dgs_files_ph"))
        src_layout.addWidget(self.input_path)
        
        btn_src = QPushButton(tr("btn_browse"))
        btn_src.clicked.connect(self.browse_input)
        src_layout.addWidget(btn_src)
        
        src_group.setLayout(src_layout)
        self.content_layout.addWidget(src_group)

        # 2. Destination
        dst_group = QGroupBox(tr("four_dgs_group_dst"))
        dst_layout = QHBoxLayout()
        
        self.output_path = QLineEdit()
        self.output_path.setText(os.path.expanduser("~/4dgs_data"))
        dst_layout.addWidget(self.output_path)
        
        btn_dst = QPushButton(tr("btn_browse"))
        btn_dst.clicked.connect(self.browse_output)
        dst_layout.addWidget(btn_dst)
        
        dst_group.setLayout(dst_layout)
        self.content_layout.addWidget(dst_group)
        
        # 3. Paramètres
        param_group = QGroupBox(tr("four_dgs_group_params"))
        param_layout = QFormLayout()
        
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(5)
        self.fps_spin.setSuffix(" fps")
        param_layout.addRow(tr("four_dgs_lbl_fps"), self.fps_spin)
        
        param_group.setLayout(param_layout)
        self.content_layout.addWidget(param_group)

        # Actions
        action_layout = QHBoxLayout()
        
        self.btn_process = QPushButton(tr("four_dgs_btn_start"))
        self.btn_process.setMinimumHeight(45)
        self.btn_process.setStyleSheet("background-color: #2A82DA; color: white; font-weight: bold;")
        self.btn_process.clicked.connect(self.toggle_process)
        action_layout.addWidget(self.btn_process)
        
        self.content_layout.addLayout(action_layout)
        
        # Add content widget to main layout
        layout.addWidget(self.content_widget)
        layout.addStretch()
        
        # Initial State
        self.content_widget.setEnabled(False)

    def browse_input(self):
        d = QFileDialog.getExistingDirectory(self, "Sélectionner dossier vidéos du projet", self.input_path.text())
        if d:
            self.input_path.setText(d)
            
    def browse_output(self):
        d = QFileDialog.getExistingDirectory(self, "Sélectionner dossier de sortie", self.output_path.text())
        if d:
            self.output_path.setText(d)

    def toggle_process(self):
        if self.processing:
            self.stopRequested.emit()
        else:
            if not self.input_path.text() or not os.path.exists(self.input_path.text()):
                QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un dossier source valide.")
                return
            if not self.output_path.text():
                QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un dossier de sortie.")
                return
                
            self.processRequested.emit()

    def set_processing_state(self, running):
        self.processing = running
        if running:
            self.btn_process.setText(tr("four_dgs_btn_stop"))
            self.btn_process.setStyleSheet("background-color: #DA2A2A; color: white; font-weight: bold;")
            self.input_path.setEnabled(False)
            self.output_path.setEnabled(False)
            self.fps_spin.setEnabled(False)
            self.chk_activate.setEnabled(False)
        else:
            self.btn_process.setText(tr("four_dgs_btn_start"))
            self.btn_process.setStyleSheet("background-color: #2A82DA; color: white; font-weight: bold;")
            self.input_path.setEnabled(True)
            self.output_path.setEnabled(True)
            self.fps_spin.setEnabled(True)
            self.chk_activate.setEnabled(True)

    def on_toggle_activation(self):
        """Logic when activation box is clicked"""
        if self.chk_activate.isChecked():
            # User wants to activate
            if not is_nerfstudio_installed():
                reply = QMessageBox.question(
                    self, 
                    tr("msg_warning"),
                    tr("msg_install_nerf"),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self.install_and_restart()
                else:
                    self.chk_activate.setChecked(False)
            else:
                self.content_widget.setEnabled(True)
        else:
            # User deactivated
            self.content_widget.setEnabled(False)

    def install_and_restart(self):
        """Install UI logic"""
        progress = QProgressDialog("Installation de Nerfstudio en cours...", "Annuler", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        
        # Simple logging callback (could signal to main window logs but for now print)
        def log_callback(line):
            print(f"[Install] {line}")
            QApplication.processEvents()
            
        success = install_nerfstudio(callback=log_callback)
        progress.close()
        
        if success:
            QMessageBox.information(
                self, 
                "Succès", 
                "Nerfstudio installé avec succès !\n\nL'application va maintenant redémarrer pour prendre en compte les changements."
            )
            # Restart Application logic
            # Assuming parent is MainWindow which has restart_application logic, 
            # OR we emit a signal, OR we use the logic from MainWindow here.
            # MainWindow handles restarts in close logic usually or explicit method.
            # Let's try to access parent's restart if available, or just quit.
            
            # Since FourDGSTab is added to tabs, parent() is the QTabWidget, parent().parent() might be MainWindow?
            # Or simpler: emit signal 'restartRequested'
            self.processRequested.emit() # Hijacking? No.
            # Add new signal? 
            # Let's rely on user manually restarting if we can't trigger it easily, 
            # BUT user asked "Checks box -> Asks to restart".
            # I can trigger a restart using sys logic I saw in MainWindow.
            
            # Or better, add restart signal to Tab and MainWindow catches it.
            # But I don't want to edit MainWindow again just for signal connection if I can avoid it.
            # Actually MainWindow already connects `relaunchRequested` from ConfigTab. I can add one here too?
            # Creating a new signal on the fly requires editing MainWindow to connect it.
            
            # Let's restart process directly here or via a clean signal.
            # I will reuse python sys.executable trick here for self-contained logic if needed, 
            # but connecting to MainWindow is cleaner. Given I am editing this file...
            # I'll let the user restart manually for safety? 
            # "Une fois coché, ça demande de redemarrer" -> implies it *requests* it.
            # "et ça install le programme" -> We just did that.
            
            import sys
            python = sys.executable
            os.execl(python, python, *sys.argv)
            
        else:
            QMessageBox.critical(self, "Erreur", "L'installation a échoué.")
            self.chk_activate.setChecked(False)

    def get_params(self):
        return {
            "enabled": self.chk_activate.isChecked(),
            "input_path": self.input_path.text(),
            "output_path": self.output_path.text(),
            "fps": self.fps_spin.value()
        }
        
    def set_params(self, params):
        if "enabled" in params:
            is_enabled = params["enabled"]
            # Only check if installed. If saved as enabled but not installed, uncheck.
            if is_enabled and is_nerfstudio_installed():
                self.chk_activate.setChecked(True)
                self.content_widget.setEnabled(True)
            else:
                self.chk_activate.setChecked(False)
                self.content_widget.setEnabled(False)
                
        if "input_path" in params: self.input_path.setText(params["input_path"])
        if "output_path" in params: self.output_path.setText(params["output_path"])
        if "fps" in params: self.fps_spin.setValue(params["fps"])
