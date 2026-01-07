import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QGroupBox, QFormLayout, QFileDialog, QCheckBox, QComboBox
)
from PyQt6.QtCore import pyqtSignal
from app.core.i18n import tr
from shutil import which

class SharpTab(QWidget):
    """Onglet de configuration Apple ML Sharp"""
    
    predictRequested = pyqtSignal()
    stopRequested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Status Check
        self.is_installed = which("sharp") is not None
        status_layout = QHBoxLayout()
        if self.is_installed:
            status_lbl = QLabel("Moteur Apple ML Sharp détecté")
            status_lbl.setStyleSheet("color: #44aa44;")
        else:
            status_lbl = QLabel("Moteur Sharp non trouvé (sera installé au lancement)")
            status_lbl.setStyleSheet("color: #aa4444; font-weight: bold;")
        status_layout.addWidget(status_lbl)
        layout.addLayout(status_layout)
        
        # Paths Group
        path_group = QGroupBox("Chemins")
        path_layout = QFormLayout()
        
        # Input Path (File or Folder)
        input_layout = QHBoxLayout()
        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText("Dossier d'images ou fichier image unique")
        self.btn_browse_input_dir = QPushButton("Dossier")
        self.btn_browse_input_dir.clicked.connect(self.browse_input_dir)
        self.btn_browse_input_file = QPushButton("Fichier")
        self.btn_browse_input_file.clicked.connect(self.browse_input_file)
        
        input_layout.addWidget(self.input_path)
        input_layout.addWidget(self.btn_browse_input_dir)
        input_layout.addWidget(self.btn_browse_input_file)
        path_layout.addRow("Input (Img/Dossier) :", input_layout)
        
        # Output Path
        output_layout = QHBoxLayout()
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Dossier de sortie pour les splats")
        self.btn_browse_output = QPushButton("...")
        self.btn_browse_output.setMaximumWidth(40)
        self.btn_browse_output.clicked.connect(self.browse_output)
        output_layout.addWidget(self.output_path)
        output_layout.addWidget(self.btn_browse_output)
        path_layout.addRow("Sortie (Output) :", output_layout)
        
        path_group.setLayout(path_layout)
        layout.addWidget(path_group)
        
        # Options Group
        opt_group = QGroupBox("Options")
        opt_layout = QFormLayout()
        
        # Checkpoint
        ckpt_layout = QHBoxLayout()
        self.ckpt_path = QLineEdit()
        self.ckpt_path.setPlaceholderText("Optionnel (Auto-download si vide)")
        self.btn_browse_ckpt = QPushButton("...")
        self.btn_browse_ckpt.setMaximumWidth(40)
        self.btn_browse_ckpt.clicked.connect(self.browse_ckpt)
        ckpt_layout.addWidget(self.ckpt_path)
        ckpt_layout.addWidget(self.btn_browse_ckpt)
        opt_layout.addRow("Checkpoint (.pt) :", ckpt_layout)
        
        # Device
        self.device_combo = QComboBox()
        self.device_combo.addItems(["default", "mps", "cpu", "cuda"])
        self.device_combo.setMinimumWidth(150)
        opt_layout.addRow("Device :", self.device_combo)
        
        # Verbose
        self.verbose_check = QCheckBox("Mode Verbose (Logs détaillés)")
        opt_layout.addRow("", self.verbose_check)
        
        opt_group.setLayout(opt_layout)
        layout.addWidget(opt_group)
        
        # Actions
        action_layout = QHBoxLayout()
        
        self.btn_run = QPushButton("Lancer Predict")
        self.btn_run.setMinimumHeight(40)
        self.btn_run.setStyleSheet("background-color: #2a82da; color: white; font-weight: bold;")
        self.btn_run.clicked.connect(self.predictRequested.emit)
            
        action_layout.addWidget(self.btn_run)
        
        self.btn_stop = QPushButton("Arrêter")
        self.btn_stop.setMinimumHeight(40)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stopRequested.emit)
        action_layout.addWidget(self.btn_stop)
        
        layout.addLayout(action_layout)
        
        layout.addStretch()
        
    def get_params(self):
        return {
            "input_path": self.input_path.text(),
            "output_path": self.output_path.text(),
            "checkpoint": self.ckpt_path.text(),
            "device": self.device_combo.currentText(),
            "verbose": self.verbose_check.isChecked()
        }

    def set_params(self, params):
        if not params: return
        
        if "input_path" in params: self.input_path.setText(params["input_path"])
        if "output_path" in params: self.output_path.setText(params["output_path"])
        if "checkpoint" in params: self.ckpt_path.setText(params["checkpoint"])
        if "device" in params: self.device_combo.setCurrentText(params["device"])
        if "verbose" in params: self.verbose_check.setChecked(params["verbose"])
        
    def browse_input_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Dossier Images")
        if path:
            self.input_path.setText(path)

    def browse_input_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Image Input", "", "Images (*.png *.jpg *.jpeg *.tif *.tiff)")
        if path:
            self.input_path.setText(path)
            
    def browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Dossier Sortie")
        if path:
            self.output_path.setText(path)
            
    def browse_ckpt(self):
        path, _ = QFileDialog.getOpenFileName(self, "Checkpoint Sharp", "", "PyTorch Model (*.pt)")
        if path:
            self.ckpt_path.setText(path)
            
    def set_processing_state(self, is_processing):
        self.btn_run.setEnabled(not is_processing)
        self.btn_stop.setEnabled(is_processing)
