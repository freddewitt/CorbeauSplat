import os
import webbrowser
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QGroupBox, QCheckBox, QFileDialog, QMessageBox, QSpinBox, QFormLayout
)
from PyQt6.QtCore import pyqtSignal, QTimer
from app.core.i18n import tr
from app.core.superplat_engine import SuperSplatEngine

class SuperSplatTab(QWidget):
    """Onglet pour SuperSplat"""
    
    stopRequested = pyqtSignal() # Pour signifier au Main Window si besoin de cleanup global
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = SuperSplatEngine()
        self.is_running = False
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header / Info
        info_label = QLabel(tr("superplat_info", "SuperSplat (PlayCanvas)"))
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Configuration Serveur
        server_group = QGroupBox(tr("group_server_config", "Configuration Serveur"))
        server_layout = QFormLayout()
        
        self.splat_port = QSpinBox()
        self.splat_port.setRange(1024, 65535)
        self.splat_port.setValue(3000)
        server_layout.addRow(tr("lbl_splat_port", "Port SuperSplat :"), self.splat_port)
        
        self.data_port = QSpinBox()
        self.data_port.setRange(1024, 65535)
        self.data_port.setValue(8000)
        server_layout.addRow(tr("lbl_data_port", "Port Données :"), self.data_port)
        
        server_group.setLayout(server_layout)
        layout.addWidget(server_group)
        
        # Données
        data_group = QGroupBox(tr("group_data", "Données à Visualiser"))
        data_layout = QVBoxLayout()
        
        path_layout = QHBoxLayout()
        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText(tr("placeholder_ply", "Chemin vers un fichier .ply ou dossier"))
        path_layout.addWidget(self.input_path)
        
        self.btn_browse = QPushButton(tr("btn_browse"))
        self.btn_browse.clicked.connect(self.browse_input)
        path_layout.addWidget(self.btn_browse)
        
        data_layout.addLayout(path_layout)
        data_group.setLayout(data_layout)
        layout.addWidget(data_group)
        
        # Options URL
        options_group = QGroupBox(tr("group_url_options", "Options de Vue"))
        options_layout = QFormLayout()
        
        self.chk_no_ui = QCheckBox(tr("check_no_ui", "Masquer l'interface (No UI)"))
        options_layout.addRow(self.chk_no_ui)
        
        self.cam_pos = QLineEdit()
        self.cam_pos.setPlaceholderText("X,Y,Z (ex: 0,1,-5)")
        options_layout.addRow(tr("lbl_cam_pos", "Position Caméra :"), self.cam_pos)
        
        self.cam_rot = QLineEdit()
        self.cam_rot.setPlaceholderText("X,Y,Z (Degrés)")
        options_layout.addRow(tr("lbl_cam_rot", "Rotation Caméra :"), self.cam_rot)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        # Actions
        action_layout = QHBoxLayout()
        
        self.btn_start = QPushButton(tr("btn_start_server", "Démarrer Serveurs"))
        self.btn_start.setMinimumHeight(40)
        self.btn_start.clicked.connect(self.toggle_server)
        action_layout.addWidget(self.btn_start)
        
        self.btn_open = QPushButton(tr("btn_open_browser", "Ouvrir Navigateur"))
        self.btn_open.setMinimumHeight(40)
        self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self.open_browser)
        action_layout.addWidget(self.btn_open)
        
        layout.addLayout(action_layout)
        layout.addStretch()
        
        self.status_label = QLabel(tr("status_stopped", "Statut : Arrêté"))
        layout.addWidget(self.status_label)

    def browse_input(self):
        """Parcourir fichier ou dossier"""
        # On preferre fichier PLY ici
        path, _ = QFileDialog.getOpenFileName(self, tr("select_ply", "Selectionner fichier PLY"), "", "Gaussian Splat (*.ply);;Tous (*.*)")
        if path:
            self.input_path.setText(path)

    def toggle_server(self):
        if self.is_running:
            self.stop_server()
        else:
            self.start_server()
            
    def start_server(self):
        # 1. Start SuperSplat
        success, msg = self.engine.start_supersplat(self.splat_port.value())
        if not success:
            QMessageBox.critical(self, tr("msg_error"), f"Erreur SuperSplat: {msg}")
            return
            
        # 2. Start Data Server (if path provided)
        path = self.input_path.text()
        if path and os.path.exists(path):
            directory = path if os.path.isdir(path) else os.path.dirname(path)
            success_data, msg_data = self.engine.start_data_server(directory, self.data_port.value())
            if not success_data:
                QMessageBox.warning(self, tr("msg_warning"), f"Erreur Serveur Données: {msg_data}")
            else:
                print(msg_data)
        
        self.is_running = True
        self.btn_start.setText(tr("btn_stop_server", "Arrêter Serveurs"))
        self.btn_start.setStyleSheet("background-color: #aa4444; color: white;")
        self.btn_open.setEnabled(True)
        self.status_label.setText(tr("status_running", "Statut : En cours d'exécution"))
        
        # Auto open? Maybe optional. For now manual.
        
    def stop_server(self):
        self.engine.stop_all()
        self.is_running = False
        self.btn_start.setText(tr("btn_start_server", "Démarrer Serveurs"))
        self.btn_start.setStyleSheet("")
        self.btn_open.setEnabled(False)
        self.status_label.setText(tr("status_stopped", "Statut : Arrêté"))

    def open_browser(self):
        """Construit l'URL et ouvre le navigateur"""
        base_url = f"http://localhost:{self.splat_port.value()}/editor" # Assume /editor path from playcanvas structure? Or just root?
        # Checked web search: https://superspl.at/editor 
        # But local serve dist usually serves root. Let's assume root first, or maybe /editor if structure dictates.
        # package.json says homepage .../editor.
        # But `serve dist` usually serves the index.html in dist.
        # If dist contains index.html directly, it's root.
        # We will try root first.
        
        url = f"http://localhost:{self.splat_port.value()}"
        
        params = []
        
        # Load Param
        path = self.input_path.text()
        if path and os.path.exists(path):
            filename = os.path.basename(path)
            # URL to data server
            data_url = f"http://localhost:{self.data_port.value()}/{filename}"
            params.append(f"load={data_url}")
            
        # No UI
        if self.chk_no_ui.isChecked():
            params.append("noui")
            
        # Camera
        if self.cam_pos.text():
            params.append(f"cameraPosition={self.cam_pos.text().strip()}")
        if self.cam_rot.text():
            params.append(f"cameraRotation={self.cam_rot.text().strip()}")
            
        if params:
            url += "?" + "&".join(params)
            
        webbrowser.open(url)
        
    def closeEvent(self, event):
        self.stop_server()
        super().closeEvent(event)
