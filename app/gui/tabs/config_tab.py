from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QGroupBox, QRadioButton, QSpinBox, QCheckBox, QMessageBox, QComboBox,
    QProgressBar, QButtonGroup
)
from PyQt6.QtCore import pyqtSignal, Qt
from app.core.i18n import tr, set_language, get_current_lang, add_language_observer
from app.gui.widgets.drop_line_edit import DropLineEdit
from app.gui.widgets.dialog_utils import get_existing_directory, get_open_file_names

class ConfigTab(QWidget):
    """Onglet de configuration principale"""
    
    # Signaux pour les actions globales qui necessitent l'orchestration du Main Window
    processRequested = pyqtSignal()
    stopRequested = pyqtSignal()
    deleteDatasetRequested = pyqtSignal()
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
        self.combo_lang.addItem("العربية", "ar")
        self.combo_lang.addItem("Русский", "ru")
        self.combo_lang.addItem("中文", "zh")
        self.combo_lang.addItem("日本語", "ja")
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

        # Mode d'entraînement
        mode_layout = QHBoxLayout()
        self.lbl_mode = QLabel(tr("label_training_mode"))
        mode_layout.addWidget(self.lbl_mode)
        
        self.combo_mode = QComboBox()
        self.combo_mode.addItem(tr("mode_gsplat"), "gsplat")
        self.combo_mode.addItem(tr("mode_sharp"), "sharp")
        self.combo_mode.addItem(tr("mode_360"), "360")
        self.combo_mode.addItem(tr("mode_4dgs"), "4dgs")
        mode_layout.addWidget(self.combo_mode)
        mode_layout.addStretch()
        input_layout.addLayout(mode_layout)
        
        # Type d'entrée (images/vidéo) - Actif uniquement pour gsplat
        type_layout = QHBoxLayout()
        self.lbl_type = QLabel(tr("label_type"))
        type_layout.addWidget(self.lbl_type)
        
        self.type_button_group = QButtonGroup(self)
        
        self.radio_images = QRadioButton(tr("radio_images"))
        self.radio_images.setChecked(True)
        self.type_button_group.addButton(self.radio_images)
        type_layout.addWidget(self.radio_images)
        
        self.radio_video = QRadioButton(tr("radio_video"))
        self.type_button_group.addButton(self.radio_video)
        type_layout.addWidget(self.radio_video)
        type_layout.addStretch()
        input_layout.addLayout(type_layout)
        self.radio_images.toggled.connect(self.update_ui_state)

        # Type de sélection (Dossier / Fichiers)
        self.source_select_layout = QHBoxLayout()
        self.lbl_source_select = QLabel(tr("label_source_select"))
        self.source_select_layout.addWidget(self.lbl_source_select)
        
        self.source_button_group = QButtonGroup(self)
        
        self.radio_source_folder = QRadioButton(tr("radio_source_folder"))
        self.radio_source_folder.setChecked(True)
        self.source_button_group.addButton(self.radio_source_folder)
        self.source_select_layout.addWidget(self.radio_source_folder)
        
        self.radio_source_files = QRadioButton(tr("radio_source_files"))
        self.source_button_group.addButton(self.radio_source_files)
        self.source_select_layout.addWidget(self.radio_source_files)
        self.source_select_layout.addStretch()
        input_layout.addLayout(self.source_select_layout)
        
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
        
        # Connect clear signals now that input_path exists
        self.radio_images.clicked.connect(self.input_path.clear)
        self.radio_video.clicked.connect(self.input_path.clear)
        self.radio_source_folder.clicked.connect(self.input_path.clear)
        self.radio_source_files.clicked.connect(self.input_path.clear)
        
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
        
        # Update visibility based on mode
        self.combo_mode.currentIndexChanged.connect(self.update_ui_state)
        
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
        
        self.chk_upscale = QCheckBox(tr("upscale_check_colmap", "Upscale (Real-ESRGAN)"))
        self.chk_upscale.setChecked(False)
        options_layout.addWidget(self.chk_upscale)
        
        options_layout.addStretch()
        self.options_group.setLayout(options_layout)
        layout.addWidget(self.options_group)
        
        # Progress Bar & Status (hidden by default)
        progress_layout = QVBoxLayout()
        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("color: #aaaaaa; font-style: italic;")
        self.lbl_status.setVisible(False)
        progress_layout.addWidget(self.lbl_status)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)
        
        layout.addLayout(progress_layout)
        
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
        """Met à jour la visibilité selon le mode d'entraînement"""
        mode = self.get_training_mode()
        is_gsplat = (mode == "gsplat")
        
        self.lbl_type.setVisible(is_gsplat)
        self.radio_images.setVisible(is_gsplat)
        self.radio_video.setVisible(is_gsplat)
        
        is_video = (mode == "gsplat" and self.radio_video.isChecked()) or (mode in ["360", "4dgs"])
        
        # FPS input is visible only if we can give video sources in theory
        self.fps_spin.setVisible(is_video)
        self.label_fps.setVisible(is_video)

        # Source selection type visibility (Gsplat and Sharp only)
        show_source_select = (mode in ["gsplat", "sharp"])
        self.lbl_source_select.setVisible(show_source_select)
        self.radio_source_folder.setVisible(show_source_select)
        self.radio_source_files.setVisible(show_source_select)
        
        # Undistort check makes sense for gsplat
        self.undistort_check.setVisible(mode == "gsplat")
        
        # Upscale check for gsplat, sharp, 360
        self.chk_upscale.setVisible(mode in ["gsplat", "sharp", "360"])
        
        # Re-translate based on dynamic mode specific checks if needed
        # We also clear path if switching modes normally makes it invalid, but for now leave as is.

    def browse_input(self):
        """Parcourir l'entrée en fonction du mode sélectionné"""
        mode = self.get_training_mode()
        
        if mode == "gsplat":
            # Uses the radio button choice instead of popup
            if self.radio_source_folder.isChecked():
                path = get_existing_directory(self, tr("group_input"))
                if path:
                    self.input_path.setText(path)
            else:
                filters = "Images (*.jpg *.jpeg *.png);;Tous (*.*)" if self.radio_images.isChecked() else "Vidéos (*.mp4 *.mov *.avi *.mkv *.MP4 *.MOV);;Tous (*.*)"
                paths, _ = get_open_file_names(
                    self, tr("group_input"),
                    "", filters
                )
                if paths:
                    self.input_path.setText("|".join(paths))

        elif mode == "sharp":
            # Uses the radio button choice instead of popup
            if self.radio_source_folder.isChecked():
                path = get_existing_directory(self, tr("group_input"))
                if path:
                    self.input_path.setText(path)
            else:
                paths, _ = get_open_file_names(
                    self, tr("group_input"),
                    "", "Images (*.jpg *.jpeg *.png);;Tous (*.*)"
                )
                if paths:
                    self.input_path.setText(paths[0]) # Enforce single image for sharp if not folder

        elif mode == "360":
            # Exactly one video
            paths, _ = get_open_file_names(
                self, tr("group_input"),
                "", "Videos (*.mp4 *.mov *.avi *.mkv *.MP4 *.MOV);;Tous (*.*)"
            )
            if paths:
                if len(paths) > 1:
                     QMessageBox.warning(self, tr("msg_warning"), tr("err_360_single_video", "Le mode 360 ne supporte qu'une vidéo."))
                self.input_path.setText(paths[0])

        elif mode == "4dgs":
            # Folder containing videos
            path = get_existing_directory(self, tr("group_input"))
            if path:
                self.input_path.setText(path)
            
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
        """Met à jour l'UI en fonction du mode/chemin"""
        if not path: return
        mode = self.get_training_mode()
        
        # Constraint checks
        if mode == "360" and "|" in str(path):
            QMessageBox.warning(self, tr("msg_warning"), tr("err_360_single_video", "Le mode 360 ne supporte qu'une vidéo."))
            path = str(path).split("|")[0]
            self.input_path.setText(path)
            
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
    
    def get_training_mode(self): return self.combo_mode.currentData()
    def set_training_mode(self, mode):
        idx = self.combo_mode.findData(mode)
        if idx >= 0:
            self.combo_mode.setCurrentIndex(idx)
            
    def get_input_type(self):
        """Returns 'video' or 'images' based on mode and radio buttons"""
        mode = self.get_training_mode()
        if mode == "gsplat":
            return "video" if self.radio_video.isChecked() else "images"
        elif mode in ["360", "4dgs"]:
            return "video"
        return "images"
    
    def get_undistort(self): return self.undistort_check.isChecked()
    def set_undistort(self, val): self.undistort_check.setChecked(val)
    
    def get_auto_brush(self): return self.chk_auto_brush.isChecked()
    def set_auto_brush(self, val): self.chk_auto_brush.setChecked(val)

    def get_upscale(self): return self.chk_upscale.isChecked()
    def set_upscale(self, val): self.chk_upscale.setChecked(val)


    
    def set_processing_state(self, processing=True):
        """Bloque ou débloque les composants UI pendant l'entrainement"""
        # Disable/Enable inputs
        self.input_group.setEnabled(not processing)
        self.output_group.setEnabled(not processing)
        self.options_group.setEnabled(not processing)
        self.chk_upscale.setEnabled(not processing)
        self.btn_delete_dataset.setEnabled(not processing)
        self.combo_lang.setEnabled(not processing)
        
        # Toggle Action Buttons
        self.btn_process.setEnabled(not processing)
        self.btn_process.setText(tr("btn_process") if not processing else tr("msg_processing"))
        if processing:
            self.btn_process.setStyleSheet("font-size: 16px; font-weight: bold; background-color: #aaaaaa; color: white;")
        else:
            self.btn_process.setStyleSheet("font-size: 16px; font-weight: bold; background-color: #2a82da; color: white;")
            
        self.btn_stop.setEnabled(processing)
        
        # Toggle Progress Visibility
        self.progress_bar.setVisible(processing)
        self.lbl_status.setVisible(processing)
        
        if processing:
            self.progress_bar.setValue(0)
            self.lbl_status.setText(tr("msg_processing", "Traitement en cours..."))
        else:
            self.progress_bar.setValue(0)
            self.lbl_status.setText("")



    def get_state(self):
        """Retourne l'état complet pour la persistance"""
        return {
            "project_name": self.get_project_name(),
            "training_mode": self.get_training_mode(),
            "input_path": self.get_input_path(),
            "output_path": self.get_output_path(),
            "fps": self.get_fps(),
            "undistort": self.get_undistort(),
            "auto_brush": self.get_auto_brush(),
            "upscale": self.get_upscale(),
            "lang": self.combo_lang.currentData()
        }

    def set_state(self, state):
        """Restaure l'état depuis le dictionnaire"""
        if not state: return
        
        if "project_name" in state: self.set_project_name(state["project_name"])
        if "training_mode" in state: self.set_training_mode(state["training_mode"])
        if "input_path" in state: self.set_input_path(state["input_path"])
        if "output_path" in state: self.set_output_path(state["output_path"])
        if "fps" in state: self.set_fps(state["fps"])
        if "undistort" in state: self.set_undistort(state["undistort"])
        if "auto_brush" in state: self.set_auto_brush(state["auto_brush"])
        if "upscale" in state: self.set_upscale(state["upscale"])
        
        # Lang is special, might require restart if changed, so we just set combo if it matches
        # or we let the main app handle valid lang loading.
        if "lang" in state:
            idx = self.combo_lang.findData(state["lang"])
            if idx >= 0: self.combo_lang.setCurrentIndex(idx)
            
        self.update_ui_state()

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
        self.lbl_mode.setText(tr("label_training_mode"))
        self.combo_mode.setItemText(0, tr("mode_gsplat"))
        self.combo_mode.setItemText(1, tr("mode_sharp"))
        self.combo_mode.setItemText(2, tr("mode_360"))
        self.combo_mode.setItemText(3, tr("mode_4dgs"))
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
        
        self.btn_process.setText(tr("btn_process") if self.btn_process.isEnabled() else tr("btn_stop"))
        self.btn_stop.setText(tr("btn_stop"))
        self.btn_quit.setText(tr("btn_quit"))
        self.btn_relaunch.setText(tr("btn_relaunch"))
        self.btn_reset.setText(tr("btn_reset"))
