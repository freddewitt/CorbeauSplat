import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QGroupBox, QRadioButton, QSpinBox, QCheckBox, QFileDialog, QMessageBox, QComboBox
)
from PyQt6.QtCore import pyqtSignal, Qt
from app.core.i18n import tr, set_language, get_current_lang, add_language_observer
from app.gui.widgets.drop_line_edit import DropLineEdit
from app.gui.widgets.dialog_utils import get_existing_directory, get_open_file_names
from app.core.extractor_360_engine import Extractor360Engine

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
    quitRequested = pyqtSignal()
    relaunchRequested = pyqtSignal()
    resetRequested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        add_language_observer(self.retranslate_ui)
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header + Language
        header_layout = QHBoxLayout()
        self.header_label = QLabel(tr("app_title"))
        self.header_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Language Selector
        self.combo_lang = QComboBox()
        self.combo_lang.addItem("Français", "fr")
        self.combo_lang.addItem("English", "en")
        self.combo_lang.addItem("Deutsch", "de")
        self.combo_lang.addItem("Italiano", "it")
        self.combo_lang.addItem("Español", "es")
        self.combo_lang.setMinimumWidth(100)
        
        # Select current language
        current = get_current_lang()
        index = self.combo_lang.findData(current)
        if index >= 0:
            self.combo_lang.setCurrentIndex(index)
            
        self.combo_lang.currentIndexChanged.connect(self.change_language)
        
        header_layout.addStretch(1)
        header_layout.addWidget(self.header_label, 2)
        header_layout.addStretch(1)
        self.lbl_lang_change = QLabel(tr("lang_change") + ":")
        header_layout.addWidget(self.lbl_lang_change)
        header_layout.addWidget(self.combo_lang)
        
        layout.addLayout(header_layout)
        
        # Groupe d'entrée
        self.input_group = QGroupBox(tr("group_input"))
        input_layout = QVBoxLayout()
        
        # Nom du Projet
        name_layout = QHBoxLayout()
        self.lbl_proj_name = QLabel(tr("label_project_name"))
        name_layout.addWidget(self.lbl_proj_name)
        self.input_project_name = QLineEdit()
        self.input_project_name.setPlaceholderText("MonProjet")
        name_layout.addWidget(self.input_project_name)
        input_layout.addLayout(name_layout)

        # Type d'entrée
        type_layout = QHBoxLayout()
        self.lbl_type = QLabel(tr("label_type"))
        type_layout.addWidget(self.lbl_type)
        self.radio_images = QRadioButton(tr("radio_images"))
        self.radio_video = QRadioButton(tr("radio_video"))
        self.radio_images.setChecked(True)
        type_layout.addWidget(self.radio_images)
        type_layout.addWidget(self.radio_video)
        type_layout.addStretch()
        input_layout.addLayout(type_layout)
        
        # Chemin
        path_layout = QHBoxLayout()
        self.lbl_path = QLabel(tr("label_path"))
        path_layout.addWidget(self.lbl_path)
        self.input_path = DropLineEdit()
        self.input_path.fileDropped.connect(self.on_input_dropped)
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
        
        self.input_group.setLayout(input_layout)
        layout.addWidget(self.input_group)
        
        # Update visibility based on type
        self.radio_images.toggled.connect(self.update_ui_state)
        self.radio_video.toggled.connect(self.update_ui_state)
        
        # Groupe de sortie
        self.output_group = QGroupBox(tr("group_output"))
        output_layout = QVBoxLayout()
        
        path_out_layout = QHBoxLayout()
        self.lbl_out_path = QLabel(tr("label_out_path"))
        path_out_layout.addWidget(self.lbl_out_path)
        self.output_path = DropLineEdit()
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
        
        # Auto Brush (reste dans Output)
        self.chk_auto_brush = QCheckBox(tr("check_auto_brush"))
        self.chk_auto_brush.setChecked(False)
        output_layout.addWidget(self.chk_auto_brush)
        
        self.output_group.setLayout(output_layout)
        layout.addWidget(self.output_group)
        
        # Nouveau Groupe: Options
        self.options_group = QGroupBox(tr("group_options"))
        options_layout = QVBoxLayout()
        
        self.undistort_check = QCheckBox(tr("check_undistort"))
        self.undistort_check.setChecked(False)
        options_layout.addWidget(self.undistort_check)
 
        # 360 Extractor
        self.check_source_360 = QCheckBox(tr("check_source_360"))
        self.check_source_360.setToolTip(tr("tip_source_360"))
        self.check_source_360.setChecked(False)
        self.check_source_360.clicked.connect(self.on_source_360_toggled)
        options_layout.addWidget(self.check_source_360)
 
        # Check if 360 engine is installed
        if not Extractor360Engine().is_installed():
            # self.check_source_360.setEnabled(False) # Removed per user request
            self.check_source_360.setToolTip(tr("360_status_missing"))
 
        self.chk_upscale = QCheckBox(tr("upscale_check_colmap"))
        self.chk_upscale.setChecked(False)
        options_layout.addWidget(self.chk_upscale)
        
        options_layout.addStretch()
        self.options_group.setLayout(options_layout)
        layout.addWidget(self.options_group)
        
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
        
        self.btn_save = QPushButton(tr("btn_save_cfg"))
        self.btn_save.clicked.connect(self.saveConfigRequested.emit)
        config_layout.addWidget(self.btn_save)
        
        self.btn_load = QPushButton(tr("btn_load_cfg"))
        self.btn_load.clicked.connect(self.loadConfigRequested.emit)
        config_layout.addWidget(self.btn_load)
        
        self.btn_open_brush = QPushButton(tr("btn_open_brush"))
        self.btn_open_brush.clicked.connect(self.openBrushRequested.emit)
        config_layout.addWidget(self.btn_open_brush)
        
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
        
        restart_layout.addSpacing(10)
        
        self.btn_reset = QPushButton(tr("btn_reset"))
        self.btn_reset.setStyleSheet("QPushButton { border: none; color: #884444; font-size: 10px; font-weight: bold; } QPushButton:hover { color: #ff0000; }")
        self.btn_reset.setFlat(True)
        self.btn_reset.clicked.connect(self.on_reset_clicked)
        restart_layout.addWidget(self.btn_reset)
        
        layout.addLayout(restart_layout)
        
        layout.addStretch()
        
        # Initial status update
        self.update_ui_state()

    def change_language(self, index):
        """Change la langue et demande redémarrage"""
        lang_code = self.combo_lang.itemData(index)
        current = get_current_lang()
        
        if lang_code != current:
            set_language(lang_code)
            # No restart needed anymore!

    def update_ui_state(self):
        """Met à jour la visibilité selon le type d'entrée"""
        is_video = self.radio_video.isChecked()
        self.fps_spin.setVisible(is_video)
        self.label_fps.setVisible(is_video)

    def browse_input(self):
        """Parcourir l'entrée"""
        if self.radio_images.isChecked():
            path = get_existing_directory(self, tr("group_input"))
            if path:
                self.input_path.setText(path)
        else:
            paths, _ = get_open_file_names(
                self, tr("group_input"),
                "", "Videos (*.mp4 *.mov *.avi *.mkv *.MP4 *.MOV);;Tous (*.*)"
            )
            if paths:
                if self.check_source_360.isChecked() and len(paths) > 1:
                     QMessageBox.warning(self, tr("msg_warning"), tr("err_360_single_video", "Le mode 360 ne supporte qu'une vidéo."))
                     paths = paths[:1]
                     
                joined_paths = "|".join(paths)
                self.input_path.setText(joined_paths)
            
    def browse_output(self):
        """Parcourir la sortie"""
        path = get_existing_directory(self, tr("group_output"))
        if path:
            self.output_path.setText(path)

    def on_input_dropped(self, path):
        """Handle drag and drop detection"""
        # This function is called when a file is dropped.
        # It should trigger the same logic as on_input_changed.
        self.on_input_changed(path)

    def on_input_changed(self, path):
        """Met à jour l'UI en fonction du type d'input"""
        if not path: return
        
        # 360 Source mode constraint: strictly single video
        if self.check_source_360.isChecked() and "|" in str(path):
            QMessageBox.warning(self, tr("msg_warning"), tr("err_360_single_video", "Le mode 360 ne supporte qu'une vidéo."))
            path = str(path).split("|")[0]
            self.input_path.setText(path)

        ext = Path(path).suffix.lower()
        if ext in ['.mp4', '.mov', '.avi', '.mkv']:
            self.radio_video.setChecked(True)
        else:
            self.radio_images.setChecked(True)
            
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

    def get_upscale(self): return self.chk_upscale.isChecked()
    def set_upscale(self, val): self.chk_upscale.setChecked(val)
    
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

    def on_source_360_toggled(self):
        """Handle 360 Source logic"""
        if self.check_source_360.isChecked():
            # Force Video mode
            self.radio_video.setChecked(True)
            self.radio_images.setEnabled(False)
            
            # Disable Upscale checkbox
            self.chk_upscale.setChecked(False)
            self.chk_upscale.setEnabled(False)
            
            # Warn if multiple videos
            path = self.input_path.text()
            if "|" in path:
                QMessageBox.warning(self, tr("msg_warning"), tr("err_360_single_video"))
                self.input_path.setText(path.split("|")[0])
        else:
            self.radio_images.setEnabled(True)
            self.chk_upscale.setEnabled(True)

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
            "upscale_active": self.get_upscale(),
            "source_360": self.check_source_360.isChecked(),
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
        if "upscale_active" in state: self.set_upscale(state["upscale_active"])
        
        # Load 360 state
        is_360 = state.get("source_360", False)
        if self.check_source_360.isEnabled():
            self.check_source_360.setChecked(is_360)
            self.on_source_360_toggled()
        
        # Lang is special, might require restart if changed, so we just set combo if it matches
        # or we let the main app handle valid lang loading.
        if "lang" in state:
            idx = self.combo_lang.findData(state["lang"])
            if idx >= 0: self.combo_lang.setCurrentIndex(idx)
            
        self.update_ui_state()

    def get_upscale_config(self, tab_params):
        """Combines local checkbox with tab params"""
        return {
            "active": self.get_upscale(),
            "model_name": tab_params.get("model_name", "RealESRGAN_x4plus"),
            "tile": tab_params.get("tile", 0),
            "target_scale": tab_params.get("scale_factor", 4),
            "face_enhance": tab_params.get("face_enhance", False)
        }
        
    def on_reset_clicked(self):
        reply = QMessageBox.question(
            self, 
            tr("btn_reset"), 
            tr("confirm_reset"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.resetRequested.emit()

    def retranslate_ui(self):
        """Met à jour les textes des widgets lors du changement de langue"""
        self.header_label.setText(tr("app_title"))
        self.lbl_lang_change.setText(tr("lang_change") + ":")
        self.input_group.setTitle(tr("group_input"))
        self.lbl_proj_name.setText(tr("label_project_name"))
        self.lbl_type.setText(tr("label_type"))
        self.radio_images.setText(tr("radio_images"))
        self.radio_video.setText(tr("radio_video"))
        self.lbl_path.setText(tr("label_path"))
        self.btn_browse_input.setText(tr("btn_browse"))
        self.label_fps.setText(tr("label_fps"))
        
        self.output_group.setTitle(tr("group_output"))
        self.lbl_out_path.setText(tr("label_out_path"))
        self.btn_browse_output.setText(tr("btn_browse"))
        self.btn_delete_dataset.setText(tr("btn_delete"))
        self.chk_auto_brush.setText(tr("check_auto_brush"))
        
        self.options_group.setTitle(tr("group_options"))
        self.undistort_check.setText(tr("check_undistort"))
        self.check_source_360.setText(tr("check_source_360"))
        self.check_source_360.setToolTip(tr("tip_source_360"))
        if not Extractor360Engine().is_installed():
             self.check_source_360.setToolTip(tr("360_status_missing"))
             
        self.chk_upscale.setText(tr("upscale_check_colmap"))
        
        self.btn_process.setText(tr("btn_process") if self.btn_process.isEnabled() else tr("btn_stop"))
        self.btn_stop.setText(tr("btn_stop"))
        self.btn_save.setText(tr("btn_save_cfg"))
        self.btn_load.setText(tr("btn_load_cfg"))
        self.btn_open_brush.setText(tr("btn_open_brush"))
        self.btn_quit.setText(tr("btn_quit"))
        self.btn_relaunch.setText(tr("btn_relaunch"))
        self.btn_reset.setText(tr("btn_reset"))
