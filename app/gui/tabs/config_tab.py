import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QGroupBox, QRadioButton, QSpinBox, QCheckBox, QFileDialog, QMessageBox, QComboBox
)
from PyQt6.QtCore import pyqtSignal, Qt
from app.core.i18n import tr, set_language, get_current_lang

class ConfigTab(QWidget):
    """Onglet de configuration principale"""
    
    # Signaux pour les actions globales qui necessitent l'orchestration du Main Window
    processRequested = pyqtSignal()
    stopRequested = pyqtSignal()
    saveConfigRequested = pyqtSignal()
    loadConfigRequested = pyqtSignal()
    openBrushRequested = pyqtSignal()
    deleteDatasetRequested = pyqtSignal()
    quitRequested = pyqtSignal()
    relaunchRequested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header + Language
        header_layout = QHBoxLayout()
        header_label = QLabel(tr("app_title"))
        header_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Language Selector
        self.combo_lang = QComboBox()
        self.combo_lang.addItem("Français", "fr")
        self.combo_lang.addItem("English", "en")
        self.combo_lang.setMinimumWidth(100)
        
        # Select current language
        current = get_current_lang()
        index = self.combo_lang.findData(current)
        if index >= 0:
            self.combo_lang.setCurrentIndex(index)
            
        self.combo_lang.currentIndexChanged.connect(self.change_language)
        
        header_layout.addStretch(1)
        header_layout.addWidget(header_label, 2)
        header_layout.addStretch(1)
        header_layout.addWidget(QLabel(tr("lang_change") + ":"))
        header_layout.addWidget(self.combo_lang)
        
        layout.addLayout(header_layout)
        
        # Groupe d'entrée
        input_group = QGroupBox(tr("group_input"))
        input_layout = QVBoxLayout()
        
        # Nom du Projet
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel(tr("label_project_name") if tr("label_project_name") != "label_project_name" else "Nom du projet :"))
        self.input_project_name = QLineEdit()
        self.input_project_name.setPlaceholderText("MonProjet")
        name_layout.addWidget(self.input_project_name)
        input_layout.addLayout(name_layout)

        # Type d'entrée
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel(tr("label_type")))
        self.radio_images = QRadioButton(tr("radio_images"))
        self.radio_video = QRadioButton(tr("radio_video"))
        self.radio_images.setChecked(True)
        type_layout.addWidget(self.radio_images)
        type_layout.addWidget(self.radio_video)
        type_layout.addStretch()
        input_layout.addLayout(type_layout)
        
        # Chemin
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel(tr("label_path")))
        self.input_path = QLineEdit()
        path_layout.addWidget(self.input_path)
        self.btn_browse_input = QPushButton(tr("btn_browse"))
        self.btn_browse_input.clicked.connect(self.browse_input)
        path_layout.addWidget(self.btn_browse_input)
        input_layout.addLayout(path_layout)
        
        # FPS (pour vidéo)
        fps_layout = QHBoxLayout()
        self.label_fps = QLabel(tr("label_fps"))
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(5)
        fps_layout.addWidget(self.label_fps)
        fps_layout.addWidget(self.fps_spin)
        fps_layout.addStretch()
        input_layout.addLayout(fps_layout)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        # Update visibility based on type
        self.radio_images.toggled.connect(self.update_ui_state)
        self.radio_video.toggled.connect(self.update_ui_state)
        
        # Groupe de sortie
        output_group = QGroupBox(tr("group_output"))
        output_layout = QVBoxLayout()
        
        path_out_layout = QHBoxLayout()
        path_out_layout.addWidget(QLabel(tr("label_out_path")))
        self.output_path = QLineEdit()
        path_out_layout.addWidget(self.output_path)
        self.btn_browse_output = QPushButton(tr("btn_browse"))
        self.btn_browse_output.clicked.connect(self.browse_output)
        path_out_layout.addWidget(self.btn_browse_output)
        output_layout.addLayout(path_out_layout)
        
        delete_layout = QHBoxLayout()
        self.btn_delete_dataset = QPushButton(tr("btn_delete"))
        self.btn_delete_dataset.clicked.connect(self.deleteDatasetRequested.emit)
        self.btn_delete_dataset.setStyleSheet("background-color: #aa4444; color: white; border: none; padding: 5px;")
        delete_layout.addWidget(self.btn_delete_dataset)
        delete_layout.addStretch()
        output_layout.addLayout(delete_layout)
        
        # Options supplémentaires
        options_layout = QHBoxLayout()
        self.undistort_check = QCheckBox(tr("check_undistort"))
        options_layout.addWidget(self.undistort_check)
        
        self.chk_auto_brush = QCheckBox(tr("check_auto_brush"))
        options_layout.addWidget(self.chk_auto_brush)
        
        output_layout.addLayout(options_layout)
        
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)
        
        # Boutons d'action
        action_layout = QHBoxLayout()
        
        self.btn_process = QPushButton(tr("btn_process"))
        self.btn_process.setMinimumHeight(50)
        self.btn_process.setStyleSheet("font-size: 16px; font-weight: bold; background-color: #2a82da; color: white;")
        self.btn_process.clicked.connect(self.processRequested.emit)
        action_layout.addWidget(self.btn_process)
        
        self.btn_stop = QPushButton(tr("btn_stop"))
        self.btn_stop.setMinimumHeight(50)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stopRequested.emit)
        action_layout.addWidget(self.btn_stop)
        
        layout.addLayout(action_layout)
        
        config_layout = QHBoxLayout()
        
        btn_save = QPushButton(tr("btn_save_cfg"))
        btn_save.clicked.connect(self.saveConfigRequested.emit)
        config_layout.addWidget(btn_save)
        
        btn_load = QPushButton(tr("btn_load_cfg"))
        btn_load.clicked.connect(self.loadConfigRequested.emit)
        config_layout.addWidget(btn_load)
        
        btn_open_brush = QPushButton(tr("btn_open_brush"))
        btn_open_brush.clicked.connect(self.openBrushRequested.emit)
        config_layout.addWidget(btn_open_brush)
        
        layout.addLayout(config_layout)
        
        layout.addStretch()
        
        # Boutons discrets pour Quitter et Relancer
        restart_layout = QHBoxLayout()
        restart_layout.addStretch()
        
        self.btn_quit = QPushButton(tr("btn_quit"))
        self.btn_quit.setStyleSheet("QPushButton { border: none; color: #888888; font-size: 10px; } QPushButton:hover { color: #ff5555; }")
        self.btn_quit.setFlat(True)
        self.btn_quit.clicked.connect(self.quitRequested.emit)
        restart_layout.addWidget(self.btn_quit)
        
        restart_layout.addSpacing(10)
        
        self.btn_relaunch = QPushButton(tr("btn_relaunch"))
        self.btn_relaunch.setStyleSheet("QPushButton { border: none; color: #888888; font-size: 10px; } QPushButton:hover { color: #ffffff; }")
        self.btn_relaunch.setFlat(True)
        self.btn_relaunch.clicked.connect(self.relaunchRequested.emit)
        restart_layout.addWidget(self.btn_relaunch)
        
        layout.addLayout(restart_layout)
        
        # Initial status update
        self.update_ui_state()

    def change_language(self, index):
        """Change la langue et demande redémarrage"""
        lang_code = self.combo_lang.itemData(index)
        current = get_current_lang()
        
        if lang_code != current:
            set_language(lang_code)
            QMessageBox.information(
                self, tr("lang_change"),
                tr("lang_restart")
            )

    def update_ui_state(self):
        """Met à jour la visibilité selon le type d'entrée"""
        is_video = self.radio_video.isChecked()
        self.fps_spin.setVisible(is_video)
        self.label_fps.setVisible(is_video)

    def browse_input(self):
        """Parcourir l'entrée"""
        if self.radio_images.isChecked():
            path = QFileDialog.getExistingDirectory(self, tr("group_input")) # Reuse string or add new? reusing group title is ok-ish
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, tr("group_input"),
                "", "Videos (*.mp4 *.mov *.avi *.mkv *.MP4 *.MOV);;Tous (*.*)"
            )
        if path:
            self.input_path.setText(path)
            
    def browse_output(self):
        """Parcourir la sortie"""
        path = QFileDialog.getExistingDirectory(self, tr("group_output"))
        if path:
            self.output_path.setText(path)
            
    # Getters/Setters pour la configuration
    def get_input_path(self): return self.input_path.text()
    def set_input_path(self, path): self.input_path.setText(path)

    def get_project_name(self): 
        text = self.input_project_name.text().strip()
        return text if text else "UntitledProject"
        
    def set_project_name(self, name): self.input_project_name.setText(name)
    
    def get_output_path(self): return self.output_path.text()
    def set_output_path(self, path): self.output_path.setText(path)
    
    def get_fps(self): return self.fps_spin.value()
    def set_fps(self, fps): self.fps_spin.setValue(fps)
    
    def get_input_type(self): return "video" if self.radio_video.isChecked() else "images"
    def set_input_type(self, type_str):
        if type_str == "video": self.radio_video.setChecked(True)
        else: self.radio_images.setChecked(True)
        
    def get_undistort(self): return self.undistort_check.isChecked()
    def set_undistort(self, val): self.undistort_check.setChecked(val)
    
    def get_auto_brush(self): return self.chk_auto_brush.isChecked()
    def set_auto_brush(self, val): self.chk_auto_brush.setChecked(val)
    
    def set_processing_state(self, is_processing):
        """Met à jour l'état des boutons pendant le traitement"""
        self.btn_process.setEnabled(not is_processing)
        self.btn_stop.setEnabled(is_processing)
        self.btn_delete_dataset.setEnabled(not is_processing)
        self.combo_lang.setEnabled(not is_processing)
        
        if is_processing:
            self.btn_process.setText(tr("btn_stop"))
            self.btn_process.setStyleSheet("font-size: 16px; font-weight: bold; background-color: #aa4444; color: white;")
        else:
            self.btn_process.setText(tr("btn_process"))
            self.btn_process.setStyleSheet("font-size: 16px; font-weight: bold; background-color: #2a82da; color: white;")

    def get_state(self):
        """Retourne l'état complet pour la persistance"""
        return {
            "project_name": self.get_project_name(),
            "input_type": self.get_input_type(),
            "input_path": self.get_input_path(),
            "output_path": self.get_output_path(),
            "fps": self.get_fps(),
            "undistort": self.get_undistort(),
            "auto_brush": self.get_auto_brush(),
            "lang": self.combo_lang.currentData()
        }

    def set_state(self, state):
        """Restaure l'état depuis le dictionnaire"""
        if not state: return
        
        if "project_name" in state: self.set_project_name(state["project_name"])
        if "input_type" in state: self.set_input_type(state["input_type"])
        if "input_path" in state: self.set_input_path(state["input_path"])
        if "output_path" in state: self.set_output_path(state["output_path"])
        if "fps" in state: self.set_fps(state["fps"])
        if "undistort" in state: self.set_undistort(state["undistort"])
        if "auto_brush" in state: self.set_auto_brush(state["auto_brush"])
        
        # Lang is special, might require restart if changed, so we just set combo if it matches
        # or we let the main app handle valid lang loading.
        if "lang" in state:
            idx = self.combo_lang.findData(state["lang"])
            if idx >= 0: self.combo_lang.setCurrentIndex(idx)
            
        self.update_ui_state()
